from RAG.Gemini_Api_connection import GeminiFunctions
from DATABASE.SQL_Database import connect
from RAG.Vector_Store import Vector
from Files_Management.Files_Parser import Chunker, ParseFile
from Security.Advance_Logger import logger
from DATABASE.Redis_Connection import redis_cache
from typing import Optional
from Security.get_secretes import load_env_from_secret
import resend
import re
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

Gemini_ = GeminiFunctions()
# Keywords
BUY_KEYWORDS = [
    "price", "pricing", "cost", "charges", "fee",
    "how much", "rate", "plan", "plans", "subscription",
    "payment", "pay", "trial", "buy", "purchase"
]

CONTACT_KEYWORDS = [
    "contact", "call", "phone", "number", "mobile",
    "whatsapp", "email", "reach", "connect",
    "meeting", "demo", "appointment", "book"
]

DECISION_KEYWORDS = [
    "interested", "want", "need", "can you help",
    "is this available", "does this work",
    "tell me more", "details", "order"
]

COMPLAINT_KEYWORDS = [
    "complain", "complaint", "issue", "problem", "bad",
    "poor", "terrible", "wrong", "mistake", "unhappy",
    "disappointed", "not satisfied", "refund"
]

ALL_KEYWORDS = BUY_KEYWORDS + CONTACT_KEYWORDS + DECISION_KEYWORDS


def contains_keyword(message: str, keywords: list) -> bool:
    """Check if message contains any keyword"""
    msg = message.lower()
    return any(k in msg for k in keywords)


def extract_phone(text: str) -> Optional[str]:
    """Extract phone number with better pattern matching"""
    patterns = [
        r'\+?\d{1,3}[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}',  # International
        r'\d{10}',  # 10 digits
        r'\+\d{12}',  # +919876543210
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group().strip()
    return False


def extract_email(text: str) -> Optional[str]:
    """Extract email with improved regex"""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(pattern, text)
    return match.group().strip() if match else False


def detect_intent(message: str) -> Optional[str]:
    """Detect user intent from message"""
    msg_lower = message.lower()
    
    if contains_keyword(msg_lower, COMPLAINT_KEYWORDS):
        return "complaint"
    elif contains_keyword(msg_lower, BUY_KEYWORDS):
        return "buying"
    elif contains_keyword(msg_lower, CONTACT_KEYWORDS):
        return "contact"
    elif contains_keyword(msg_lower, DECISION_KEYWORDS):
        return "decision"
    return None

class EmbeddingsALL:
    @staticmethod
    def send_escalation_email(customer_query: str, history: str, visitor_id: str, contact_info: str, receiver_email: str):
        try:
            resend.api_key = load_env_from_secret("RESEND_API_KEY")

            if not resend.api_key or not receiver_email:
                logger.error("Resend API key or receiver email missing")
                return False

            subject = f"🚨 Escalated Support Ticket — Visitor ID: {visitor_id}"

            html_body = f"""
            <h2>🚨 New Escalated Support Ticket</h2>
            <p><strong>Visitor ID:</strong> {visitor_id}</p>
            <p><strong>Contact Info:</strong> {contact_info}</p>
            
            <h3>Customer Query</h3>
            <p>{customer_query}</p>
            
            <h3>Chat History</h3>
            <pre style="background:#f4f4f4;padding:12px;border-radius:6px;">{history}</pre>
            """

            params = {
                "from": "onboarding@resend.dev", # ← Change this to your verified domain
                "to": [receiver_email],
                "subject": subject,
                "html": html_body,
            }

            email = resend.Emails.send(params)
            logger.info(f"Escalation email sent successfully. ID: {email.get('id')}")
            return True

        except Exception as e:
            logger.error("Failed to send escalation email via Resend", e)
            return False

    @staticmethod
    async def generate_and_store_embeddings(user_id: int, file_name: str, extension: str, Text: str):
        try:
            document_id = connect.add_document(user_id=user_id, file_name=file_name, extension=extension)
            if not document_id:
                return False

            ext_lower = extension.lower()
            if ext_lower in ParseFile.CODE_EXTENSIONS and ext_lower != ".txt":
                parent_chunks = Chunker.chunk_code(Text, ext_lower)
            else:
                parent_chunks = await Chunker.chunk_text_semantically(Text)

            ans = await Vector.add_vectors_batch(user_id=user_id, chunks=parent_chunks, document_id=document_id)
            if ans:
                return True
            
            return False
        except Exception as e:
            logger.error("EmbeddingALL.generate_and_store_embeddings", e)
            return False
        
    @staticmethod
    async def answer_from_embeddings(user_id: int, user_query: str, visitor_id: str) -> str:
        try:
            msg_lower = user_query.lower().strip()

            if msg_lower == "help":
                help_output = (
                    "👋 *How can I speed up your day?*\n\n"
                    "• Ask any specific question about our docs\n"
                    "• Type **'complain'** to open an ticket handoff to our team\n"
                )
                return help_output
            
            current_state = connect.get_or_create_client_state(user_id=user_id, visitor_id=visitor_id)
            if current_state == "NEW":
                result = await EmbeddingsALL.invoke(user_id=user_id, user_query=user_query, visitor_id=visitor_id)
                connect.set_client_state(user_id=user_id, visitor_id=visitor_id, state="ACTIVE")
                return result + "\n\nI'm your assistant today. Type 'help' to see what I can do. 😊"
            
            if current_state == "EXTRACTING_CONTACT":
                phone = extract_phone(user_query)
                email = extract_email(user_query)
                if phone or email:
                    contact_payload = phone or email
                    if connect.save_client_lead(user_id=user_id, visitor_id=visitor_id, contact_data=contact_payload):
                        raw_history = connect.get_recent_chat_history(user_id=user_id, visitor_id=visitor_id, limit=6) or []
                        history_context = ""
                        for turn in raw_history:
                            speaker = "User" if turn["role"] == "user" else "Support Agent"
                            clipped_text = turn["text"][:300] + "..." if len(turn["text"]) > 300 else turn["text"]
                            history_context += f"{speaker}: {clipped_text}\n"
                        client_email = connect.get_email_by_user_id(user_id=user_id)

                        asyncio.create_task(
                        asyncio.to_thread(
                            EmbeddingsALL.send_escalation_email,
                            customer_query=user_query,
                            history=history_context,
                            visitor_id=visitor_id,
                            contact_info=contact_payload,
                            receiver_email=client_email
                        )
                        )
                        response = "✅ Your complaint has been recorded. Our team will contact you soon to resolve this. Thank you for your patience! 🙏"
                        connect.set_client_state(user_id=user_id, visitor_id=visitor_id, state="ACTIVE")
                        return response
                else:
                    result = await EmbeddingsALL.invoke(user_id=user_id, user_query=user_query, visitor_id=visitor_id)
                    return result + "Please provide your **email** or **Phone**"
                
            if current_state == "HANDLING_COMPLAINT":
                response = "✅ Thank you for sharing this. Our support team will review it within 24 hours.\n\n📩 To ensure we can reach you, please share your *phone number or email*."
                connect.set_client_state(user_id=user_id, visitor_id=visitor_id, state="EXTRACTING_CONTACT")
                connect.save_chat_turn(user_id=user_id, visitor_id=visitor_id, role="user", message=user_query)
                connect.save_chat_turn(user_id=user_id, visitor_id=visitor_id, role="model", message=response)
                return response
            
            if msg_lower == "complain" or contains_keyword(msg_lower, COMPLAINT_KEYWORDS):
                response = "I'm really sorry to hear you're facing an issue 😔\n\nPlease share the details, and I'll make sure our team addresses this. Your satisfaction matters to us! 🙏"
                connect.set_client_state(user_id=user_id, visitor_id=visitor_id, state="HANDLING_COMPLAINT")
                connect.save_chat_turn(user_id=user_id, visitor_id=visitor_id, role="user", message=user_query)
                connect.save_chat_turn(user_id=user_id, visitor_id=visitor_id, role="model", message=response)
                return response

            return await EmbeddingsALL.invoke(user_id=user_id, user_query=user_query, visitor_id=visitor_id)
        except Exception as e:
            logger.error("EmbeddingsALL.answer_from_embeddings", e)
            return "Try again later!"
    
    @staticmethod
    async def invoke(user_id: int, user_query: str, visitor_id: str) -> str:
        top_k_chunks = await Vector.search_vector(query=user_query, user_id=user_id, limit=4)
        
        seen_chunks = set()
        retrieved_documents = ""
        idx = 1

        for item in top_k_chunks:
            chunk_text = item["text"]
            if chunk_text not in seen_chunks:
                seen_chunks.add(chunk_text)
                
                chunk = item.get("parent_context", chunk_text)
                if len(chunk) > 1500:
                    chunk = chunk[:1500] + " [Truncated]"
                    
                retrieved_documents += f"[Document Source #{idx}]: {chunk}\n\n"
                idx += 1

        raw_history = connect.get_recent_chat_history(user_id=user_id, visitor_id=visitor_id, limit=6) or []
        history_context = ""
        for turn in raw_history:
            speaker = "User" if turn["role"] == "user" else "Support Agent"
            clipped_text = turn["text"][:300] + "..." if len(turn["text"]) > 300 else turn["text"]
            history_context += f"{speaker}: {clipped_text}\n"

        system_instruction = (
            "You are an elite, energetic, and highly structured AI Customer Support Specialist.\n"
            "Your tone must be playful yet deeply respectful, professional, and empathetic. Use crisp, formatted layout structures to make answers scannable.\n\n"
            
            "STYLE & BEHAVIOR RULES:\n"
            "1. Structured Scannability: Never emit large blocks of dense text. Use clean bullet points, bold key technical terms, and brief clear headings for distinct steps.\n"
            "2. Tone Balance: Be engaging and dynamic (e.g., use phrases like 'Let's get this sorted for you!', 'Great question!', 'You're all set!'). Always remain respectful and customer-centric.\n"
            "3. Grounded Playfulness: You can use occasional context-appropriate professional emojis (e.g., 👋, 🚀, 🛠️, ✅) to drive energy, but do not sacrifice technical accuracy.\n"
            "4. Boundary Handling: Base your answers cleanly on the provided Document Sources. If the information is missing, do not say 'I don't know.' Instead, maintain a helpful attitude: 'I couldn't find that exact detail in our current workspace docs, but I can get a human teammate to look into this for you right away! Should I open an escalation ticket?'\n"
        )

        final_prompt = (
            f"{system_instruction}\n"
            f"=== VERIFIED DOCUMENT SOURCES ===\n"
            f"{retrieved_documents or 'No direct documentation found for this query.'}\n\n"
            f"=== RECENT CHAT HISTORY ===\n"
            f"{history_context or 'No prior history.'}\n\n"
            f"Customer Query: {user_query}\n\n"
            f"Support Agent Answer Structure:\n"
            f"1. Friendly Opening\n"
            f"2. Structured Resolution (Bullet points/Bold terms)\n"
            f"3. Clear Next Steps or Follow-up Check\n\n"
            f"Support Agent Answer:"
        )

        bot_response = await Gemini_.generate_response(query=final_prompt)
        if not bot_response:
            bot_response = "I encountered an error generating a response."

        connect.save_chat_turn(user_id=user_id, visitor_id=visitor_id, role="user", message=user_query)
        connect.save_chat_turn(user_id=user_id, visitor_id=visitor_id, role="model", message=bot_response)

        return bot_response
    
if __name__ == "__main__":
    print(EmbeddingsALL.send_escalation_email("Nothing", "Yo", "v2ufs", "9999999999", "nirvishpatel622@gmail.com"))
