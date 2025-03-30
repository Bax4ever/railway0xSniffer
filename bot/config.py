from dotenv import load_dotenv
import os

load_dotenv()  # Make sure you call this if using a `.env` file

TRACKADEMYBOT = os.getenv("TRACKADEMYBOT")
INFURA_URL = os.getenv("INFURA_URL")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
GRAPH_API_KEY = os.getenv("GRAPH_API_KEY")
BOTBUNDLER_TOKEN = os.getenv("BOTBUNDLER_TOKEN")
GRAPHQL_URL = os.getenv("GRAPHQL_URL")
MORALIS_API_KEY = os.getenv("MORALIS_API_KEY")
ANKR_URL = os.getenv("ANKR_URL")
ANKR_API = os.getenv("ANKR_API")
RAILWAY_PUBLIC_URL = os.getenv("RAILWAY_PUBLIC_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
