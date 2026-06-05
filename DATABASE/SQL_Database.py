#Run via python -m DATABASE.SQL_Database
import uuid
from sqlalchemy import create_engine, text
from Security.Advance_Logger import logger
from Security.get_secretes import load_env_from_secret
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

class UserConnection:
    def __init__(self):
        self.engine = create_engine(load_env_from_secret("DATABASE_URL"))
        self.ph = PasswordHasher()
        self.create_table()
        self.create_document_table()
        self.create_chat_history_table()
        self.create_client_table()

    # Create users table
    def create_table(self):
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT UNIQUE NOT NULL,
                        url TEXT NOT NULL,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL
                    )
                """))

                conn.commit()
        except Exception as e:
            logger.error("UserConnection.create_table", e)

    def create_document_table(self):
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        file_name TEXT NOT NULL,
                        extension TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id)
                            REFERENCES users(id)
                            ON DELETE CASCADE
                    )
                """))
                conn.commit()
            return True
        except Exception as e:
            logger.error(
                f"UserConnection.create_document_table", e
            )
            return False
        
    def create_client_table(self):
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS clients (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        visitor_id TEXT NOT NULL,
                        email TEXT NULL,
                        phone TEXT NULL,
                        state TEXT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id)
                            REFERENCES users(id)
                            ON DELETE CASCADE
                    )
                """))
                conn.commit()
            return True
        except Exception as e:
            logger.error(
                f"UserConnection.create_document_table", e
            )
            return False
    
    def create_chat_history_table(self) -> bool:
        """
        Creates the chat_history partition table with indexing constraints for multi-tenant isolation.
        """
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        visitor_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        message TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id)
                            REFERENCES users(id)
                            ON DELETE CASCADE
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_chat_history_user_date 
                    ON chat_history (user_id, created_at DESC);
                """))
                conn.commit()
            return True
        except Exception as e:
            logger.error("UserConnection.create_chat_history_table", e)
            return False

    # Create new user
    def create_user(self, name, url, email, password):
        try:
            user_id = str(uuid.uuid4())
            hashed_password = self.ph.hash(password)
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        INSERT INTO users (
                            user_id,
                            url,
                            name,
                            email,
                            password
                        )
                        VALUES (
                            :user_id,
                            :url,
                            :name,
                            :email,
                            :password
                        )
                        RETURNING user_id
                    """),
                    {
                        "name": name,
                        "user_id": user_id,
                        "url": url,
                        "email": email,
                        "password": hashed_password
                    }
                )
                document = result.fetchone()
                conn.commit()
                return document.user_id
            
        except Exception as e:
            logger.error("UserConnection.create_user", e)
            return False

    # Get user by email
    def get_user_by_email(self, email):
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        SELECT *
                        FROM users
                        WHERE email = :email
                    """),
                    {
                        "email": email
                    }
                )

                return result.fetchone()
        except Exception as e:
            logger.error("UserConnection.get_user_by_email", e)

    def get_user_by_id(self, id: int) -> bool:
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        SELECT *
                        FROM users
                        WHERE id = :id
                    """),
                    {
                        "id": id
                    }
                )

                return result.fetchone()
        except Exception as e:
            logger.error("UserConnection.get_user_by_id", e)

    # Verify login
    def login_user(self, email: str, password: str) -> dict:
        user = self.get_user_by_email(email)
        if not user:
            return False
        try:
            self.ph.verify(
                user.password,
                password
            )

            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "user_id": user.user_id
            }
        except VerifyMismatchError:
            return False
        
    def get_Id_From_email(self, email: str) -> int:
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        SELECT id
                        FROM users
                        WHERE email = :email
                    """),
                    {
                        "email": email
                    }
                )

                row = result.fetchone()

                if row:
                    return row.id
                
                return None
        except Exception as e:
            logger.error("UserConnection.get_Id_From_email", e)
            return ""

    def get_Id_From_client_token(self, client_token: str) -> int:
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        SELECT id
                        FROM users
                        WHERE user_id = :client_token
                    """),
                    {
                        "client_token": client_token
                    }
                )

                row = result.fetchone()

                if row:
                    return row.id
                
                return None
        except Exception as e:
            logger.error("UserConnection.get_Id_From_email", e)
            return ""
        
    def get_email_by_user_id(self, user_id: int) -> str:
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        SELECT email
                        FROM users
                        WHERE id = :user_id
                    """),
                    {
                        "user_id": user_id
                    }
                )

                row = result.fetchone()

                if row:
                    return row.email
                
                return None
        except Exception as e:
            logger.error("UserConnection.get_Id_From_email", e)
            return ""

    def add_document( self, user_id: int, file_name: str, extension: str ):
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        INSERT INTO documents (
                            user_id,
                            file_name,
                            extension
                        )
                        VALUES (
                            :user_id,
                            :file_name,
                            :extension
                        )
                        RETURNING id
                    """),
                    {
                        "user_id": user_id,
                        "file_name": file_name,
                        "extension": extension
                    }
                )
                document = result.fetchone()
                conn.commit()
                return document.id
            
        except Exception as e:
            logger.error(
                f"UserConnection.add_document", e
            )
            return None
        
    def delete_document(self, user_id: int, document_id: int) -> bool:
        try:
            with self.engine.begin() as conn:
                result=conn.execute(
                    text("""
                        DELETE FROM documents
                        WHERE id=:document_id
                        AND user_id=:user_id
                    """),
                    {
                        "document_id":document_id,
                        "user_id": user_id
                    }
                )
                conn.commit()
                return result.rowcount>0

        except Exception as e:
            logger.error(
                f"UserConnection.delete_document", e
            )
            return False
    
    def get_documents_data_by_userId(self, user_id: int) -> list[dict]:
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        SELECT id, file_name, extension, created_at
                        FROM documents
                        WHERE user_id = :user_id
                    """),
                    {"user_id": user_id}
                )

                documents = [dict(row._mapping) for row in result]

                return documents

        except Exception as e:
            logger.error("UserConnection.get_documents_data_by_userID", e)
            return False
        
    def save_chat_turn(self, user_id: int, role: str, message: str, visitor_id: str) -> bool:
        """
        Inserts a single chat turn metadata payload under explicit user boundary ownership.
        """
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO chat_history (user_id, visitor_id, role, message)
                        VALUES (:user_id, :visitor_id, :role, :message)
                    """),
                    {
                        "user_id": user_id,
                        "visitor_id": visitor_id,
                        "role": role,
                        "message": message
                    }
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error("UserConnection.save_chat_turn", e)
            return False

    def get_recent_chat_history(self, user_id: int, visitor_id: str, limit: int = 6) -> list[dict]:
        """
        Retrieves the latest exchanges for a user sorted chronologically (oldest to newest).
        """
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        SELECT role, message AS text
                        FROM chat_history
                        WHERE user_id = :user_id
                        AND visitor_id = :visitor_id
                        ORDER BY created_at DESC
                        LIMIT :limit
                    """),
                    {
                        "user_id": user_id,
                        "visitor_id" : visitor_id,
                        "limit": limit
                    }
                )
                
                # Convert SQLAlchemy row objects to dictionary mappings
                history = [dict(row._mapping) for row in result]
                
                # Reverse the list in memory to restore proper chronological timeline order: [User, Model, User...]
                history.reverse()
                return history
            
        except Exception as e:
            logger.error("UserConnection.get_recent_chat_history", e)
            return []
        
    def add_client(self, user_id: int, visitor_id: str) -> int:
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        INSERT INTO documents (
                            user_id,
                            visitor_id,
                            state
                        )
                        VALUES (
                            :user_id,
                            :visitor_id
                            :state
                        )
                        RETURNING state
                    """),
                    {
                        "user_id": user_id,
                        "visitor_id": visitor_id,
                        "state": "NEW"
                    }
                )
                document = result.fetchone()
                conn.commit()
                return document.id
            
        except Exception as e:
            logger.error(
                f"UserConnection.add_document", e
            )
            return None

    def get_or_create_client_state(self, user_id: int, visitor_id: str) -> str:
        """
        Fetches the active customer operational tracking state. 
        If the visitor is new, initializes their entry inside the clients table.
        """
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        SELECT state FROM clients 
                        WHERE user_id = :user_id AND visitor_id = :visitor_id
                    """),
                    {"user_id": user_id, "visitor_id": visitor_id}
                )
                row = result.fetchone()
                if row:
                    return row.state

                # If entry doesn't exist, create a new record entry
                conn.execute(
                    text("""
                        INSERT INTO clients (user_id, visitor_id, state)
                        VALUES (:user_id, :visitor_id, 'NEW')
                    """),
                    {"user_id": user_id, "visitor_id": visitor_id}
                )
                conn.commit()
            return "NEW"
        except Exception as e:
            logger.error("UserConnection.get_or_create_client_state", e)
            return "ACTIVE"

    def set_client_state(self, user_id: int, visitor_id: str, state: str) -> bool:
        """Updates the tracking state constraint of an active visitor."""
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE clients SET state = :state
                        WHERE user_id = :user_id AND visitor_id = :visitor_id
                    """),
                    {"state": state, "user_id": user_id, "visitor_id": visitor_id}
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error("UserConnection.set_client_state", e)
            return False

    def save_client_lead(self, user_id: int, visitor_id: str, contact_data: str) -> bool:
        """
        Parses context to cleanly bind contact info parameters inside columns.
        """
        try:
            is_email = "@" in contact_data
            with self.engine.begin() as conn:
                if is_email:
                    conn.execute(
                        text("""
                            UPDATE clients 
                            SET email = :contact, state = 'ESCALATED', created_at = CURRENT_TIMESTAMP
                            WHERE user_id = :user_id AND visitor_id = :visitor_id
                        """),
                        {"contact": contact_data, "user_id": user_id, "visitor_id": visitor_id}
                    )
                else:
                    conn.execute(
                        text("""
                            UPDATE clients 
                            SET phone = :contact, state = 'ESCALATED', created_at = CURRENT_TIMESTAMP
                            WHERE user_id = :user_id AND visitor_id = :visitor_id
                        """),
                        {"contact": contact_data, "user_id": user_id, "visitor_id": visitor_id}
                    )
                conn.commit()
            return True
        except Exception as e:
            logger.error("UserConnection.save_client_lead", e)
            return False
        
    def update_user_allowed_url(self, user_id: int, allowed_url: str) -> bool:
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE users
                        SET url = :allowed_url
                        WHERE id = :user_id
                    """),
                    {
                        "allowed_url": allowed_url,
                        "user_id": user_id
                    }
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error("UserConnection.update_user_allowed_url", e)
            return False
        
    def get_client_data_by_userid(self, user_id: int):
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("""
                        SELECT *
                        FROM clients
                        WHERE user_id = :user_id
                    """),
                    {
                        "user_id": user_id
                    }
                )

                return result.fetchone()
        except Exception as e:
            logger.error("UserConnection.get_user_by_id", e)
            return False

connect = UserConnection()

if __name__ == "__main__":
    UserConnection().create_document_table()