# Environment Configuration
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class EnvConfig:
    """Environment configuration class for managing all environment variables"""
    
    DB_TYPE = os.getenv('DB_TYPE', 'sqlite').lower()  
    DB_NAME = os.getenv('DB_NAME', 'visualflow_db')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_SSL_REQUIRE = os.getenv('DB_SSL_REQUIRE', 'false').lower() == 'true'
    DB_SSL_MODE = os.getenv('DB_SSL_MODE', 'prefer')
    DB_SSL_CERT_PATH = os.getenv('DB_SSL_CERT_PATH', '')
    DB_SSL_KEY_PATH = os.getenv('DB_SSL_KEY_PATH', '')
    DB_SSL_CA_PATH = os.getenv('DB_SSL_CA_PATH', '')
    DB_SSL_CA_CERT = os.getenv('DB_SSL_CA_CERT', '')
    
    @classmethod
    def get_ca_cert_file(cls):
        if cls.DB_SSL_CA_CERT and not cls.DB_SSL_CA_PATH:
            import tempfile
            import os as _os
            
            # Create temp file for CA cert
            temp_fd, temp_path = tempfile.mkstemp(suffix='.pem', prefix='ca_cert_')
            try:
                with _os.fdopen(temp_fd, 'w') as temp_file:
                    temp_file.write(cls.DB_SSL_CA_CERT)
                return temp_path
            except Exception:
                _os.unlink(temp_path)
                return None
        return cls.DB_SSL_CA_PATH
    
    # AI/ML API Keys
    GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
    LANGCHAIN_API_KEY = os.getenv('LANGCHAIN_API_KEY', '')
    LANGCHAIN_TRACING_V2 = os.getenv('LANGCHAIN_TRACING_V2', 'true')
    LANGCHAIN_PROJECT = os.getenv('LANGCHAIN_PROJECT', 'visualflow')
    
    # Django Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-this-in-production')
    DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')
    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS').split(',')
    
    # Application Configuration
    APP_NAME = os.getenv('APP_NAME', 'VisualFlow')
    APP_VERSION = os.getenv('APP_VERSION', '1.0.0')
    # ---- APP MODE SWITCH ----
    APP_MODE = os.getenv("APP_MODE", "development").lower()
    ENABLE_BROWSER_RELOAD = APP_MODE != "production"

    
    @classmethod
    def get_database_url(cls):
        """Get database URL for Django"""
        return f'postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}'
    
    @classmethod
    def validate_required_env_vars(cls):
        """Validate that all required environment variables are set"""
        required_vars = [
            'GROQ_API_KEY',
            'DB_PASSWORD'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True