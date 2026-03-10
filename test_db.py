from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

uri = os.getenv("MONGODB_URI")

client = MongoClient(uri)

db = client[os.getenv("DB_NAME")]

print("Connected successfully")

print("Collections:", db.list_collection_names())