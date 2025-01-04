from app.database import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_connection():
    try:
        with engine.connect() as connection:
            result = connection.execute(text('SELECT 1'))
            logger.info('Successfully connected to database!')
            
            logger.info('Tables in database:')
            result = connection.execute(text('SHOW TABLES'))
            tables = [row[0] for row in result]
            for table in tables:
                logger.info(f'- {table}')
                
                # Get table structure
                result = connection.execute(text(f'DESCRIBE {table}'))
                logger.info(f'  Columns:')
                for row in result:
                    logger.info(f'    - {row[0]}: {row[1]}')
            
            return True
    except Exception as e:
        logger.error(f'Error connecting to database: {e}')
        return False

if __name__ == '__main__':
    test_database_connection()
