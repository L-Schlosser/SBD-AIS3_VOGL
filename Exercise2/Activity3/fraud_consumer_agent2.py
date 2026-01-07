#This agent uses a sliding window (simulated) to perform velocity checks and score the transaction
import json
import base64
from collections import deque
import time
from kafka import KafkaConsumer
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Kafka configuration
KAFKA_BROKER = "localhost:9094"
KAFKA_TOPIC = "dbserver1.public.transactions"
CONSUMER_GROUP = "fraud-detection-agent2"

# Simulated In-Memory State for Velocity Checks
user_history = {}

def decode_decimal(encoded_bytes):
    """Decode Debezium base64-encoded Decimal to float."""
    if isinstance(encoded_bytes, str):
        # Base64 string → bytes → interpret as big-endian signed int → divide by scale (10^2)
        try:
            decoded = base64.b64decode(encoded_bytes)
            # Debezium Decimal with scale=2: interpret as big-endian signed int, then divide by 100
            amount_int = int.from_bytes(decoded, byteorder='big', signed=True)
            return amount_int / 100.0
        except Exception as e:
            logger.warning(f"Failed to decode amount {encoded_bytes}: {e}")
            return 0.0
    return float(encoded_bytes)

def analyze_fraud(transaction):
    """Perform velocity checks and heuristic fraud scoring."""
    user_id = transaction['user_id']
    amount = decode_decimal(transaction['amount'])  # Decode here
    
    # 1. Velocity Check (recent transaction count in last 60 seconds)
    now = time.time()
    if user_id not in user_history:
        user_history[user_id] = deque()
    
    # Keep only last 60 seconds of history
    user_history[user_id].append(now)
    while user_history[user_id] and user_history[user_id][0] < now - 60:
        user_history[user_id].popleft()

    velocity = len(user_history[user_id])
    
    # 2. Heuristic Fraud Scoring
    score = 0
    if velocity > 5:
        score += 40  # Too many transactions in a minute
    if amount > 4000:
        score += 50  # High value transaction
    if transaction['card_type'] == 'AMEX':
        score += 10  # Higher risk for AMEX
    
    return score, amount  # Return decoded amount too

def main():
    logger.info("⚡ Agent2 (Velocity & Heuristic) starting...")
    
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
            # Debezium wraps data in 'payload' → 'after' structure
            payload = message.value.get('payload', {})
            data = payload.get('after')
            
            if data:
                fraud_score, decoded_amount = analyze_fraud(data)
                
                if fraud_score > 70:
                    logger.warning(
                        f"⚠️ HIGH FRAUD ALERT: User {data['user_id']} | "
                        f"Score: {fraud_score} | Amount: ${decoded_amount:.2f}"
                    )
                else:
                    logger.info(
                        f"✅ Transaction OK: Score {fraud_score} | Amount: ${decoded_amount:.2f}"
                    )
    
    except KeyboardInterrupt:
        logger.info("⛔ Agent2 stopped.")
    finally:
        consumer.close()

if __name__ == "__main__":
    main()