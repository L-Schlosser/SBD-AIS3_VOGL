from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, count, window, from_unixtime
from pyspark.sql.types import StructType, StructField, StringType, LongType

# Configuration & Session Setup
CHECKPOINT_PATH = "/tmp/spark-checkpoints/crash-monitoring"

spark = (
    SparkSession.builder
    .appName("CrashMonitoring")
    .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_PATH)
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")

# Define schema - timestamp is in Unix epoch format (seconds)
schema = StructType([
    StructField("timestamp", LongType()), 
    StructField("status", StringType()),
    StructField("severity", StringType()),
    StructField("source_ip", StringType()),
    StructField("user_id", StringType()),
    StructField("content", StringType())
])

# Read Stream from Kafka
raw_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "kafka:9092")
    .option("subscribe", "logs")
    .option("startingOffsets", "earliest")
    .option("failOnDataLoss", "false")
    .load()
)

# Processing, Filtering & Time-Based Aggregation
parsed_df = (
    raw_df.select(from_json(col("value").cast("string"), schema).alias("data"))
    .select("data.*")
)

# Convert Unix timestamp to proper timestamp type
timestamped_df = parsed_df.withColumn(
    "event_time", 
    from_unixtime(col("timestamp")).cast("timestamp")
)

filtered_df = timestamped_df

# Group by 10-second time windows and user_id, then aggregate
windowed_df = (
    filtered_df
    .withWatermark("event_time", "30 seconds")  # Handle late arrivals
    .groupBy(
        window(col("event_time"), "10 seconds"),
        col("user_id")
    )
    .agg(count("*").alias("crash_count"))
)


windowed_df = windowed_df.filter(col("crash_count") > 2)

critical_users_df = (
    windowed_df
    .select(
        col("window").alias("Interval"),
        col("user_id"),
        col("crash_count")
    )
)

# Writing - Output to console
query = (
    critical_users_df.writeStream
    .outputMode("update")
    .format("console")
    .option("truncate", "false")
    .start()
)

query.awaitTermination()
