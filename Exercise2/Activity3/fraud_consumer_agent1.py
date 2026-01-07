# This agent calculates a running average for each user and flags transactions that are significantly higher than their usual behavior (e.g., $3\sigma$ outliers).

import json
import base64
import logging
import statistics
from kafka import KafkaConsumer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Kafka configuration
KAFKA_BROKER = "localhost:9094"  # EXTERNAL listener from docker-compose
KAFKA_TOPIC = "dbserver1.public.transactions"
CONSUMER_GROUP = "fraud-detection-agent1"

# In-memory store for user spending patterns
user_spending_profiles = {}

def decode_decimal(encoded_bytes):
    """Decode Debezium base64-encoded Decimal to float."""
    if isinstance(encoded_bytes, str):
        try:
            decoded = base64.b64decode(encoded_bytes)
            amount_int = int.from_bytes(decoded, byteorder='big', signed=True)
            return amount_int / 100.0
        except Exception as e:
            logger.warning(f"Failed to decode amount {encoded_bytes}: {e}")
            return 0.0
    return float(encoded_bytes)

def analyze_pattern(data):
    """Detect anomalies based on spending history (3-sigma outlier detection)."""
    user_id = data['user_id']
    amount = decode_decimal(data['amount'])  # Decode here
    
    if user_id not in user_spending_profiles:
        user_spending_profiles[user_id] = []
    
    history = user_spending_profiles[user_id]
    is_anomaly = False
    
    if len(history) >= 3:
        avg = statistics.mean(history)
        stdev = statistics.stdev(history)
        
        if amount > (avg + 3 * stdev):
            is_anomaly = True
    
    history.append(amount)
    if len(history) > 50:
        history.pop(0)
    
    return is_anomaly, amount  # Return decoded amount

def main():
    logger.info("🧬 Agent1 (Anomaly Detection) starting...")
    
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_BROKER],
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda x: json.loads(x.decode('utf-8')),
        auto_offset_reset='earliest',
        enable_auto_commit=True
    )
    
    try:
        for message in consumer:
            payload = message.value.get('payload', {})
            data = payload.get('after')
            
            if data:
                is_anomaly, decoded_amount = analyze_pattern(data)
                
                if is_anomaly:
                    logger.warning(
                        f"🚨 ANOMALY DETECTED: User {data['user_id']} | "
                        f"Amount: ${decoded_amount:.2f} | Card: {data['card_type']}"
                    )
                else:
                    logger.info(
                        f"✅ Transaction OK: User {data['user_id']} | Amount: ${decoded_amount:.2f}"
                    )
    
    except KeyboardInterrupt:
        logger.info("⛔ Agent1 stopped.")
    finally:
        consumer.close()

if __name__ == "__main__":
    main()