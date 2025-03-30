from bot.config import GRAPHQL_URL
import requests

def get_liquidity_pair_details(pair_id):
    """
    Fetch details for the specified liquidity pair.
    Handles errors gracefully and returns default values in case of an error.
    """
    try:
        # GraphQL query to get pair details
        query = """
        {
          pairs(where: {id: "%s"}) {
            reserveUSD
            reserve0
            reserve1
            txCount
            volumeToken1
          }
        }
        """ % pair_id

        # Make the API request
        response = requests.post(GRAPHQL_URL, json={'query': query}, timeout=10)
        response.raise_for_status()  # Raise an error for bad status codes

        # Parse the response JSON data
        data = response.json()

        # Check if 'pairs' data exists in the response
        if 'data' in data and 'pairs' in data['data'] and len(data['data']['pairs']) > 0:
            pair_data = data['data']['pairs'][0]
            return {
                "reserveUSD": float(pair_data['reserveUSD']),
                "reserve0": float(pair_data['reserve0']),
                "reserve1": float(pair_data['reserve1']),
                "txCount": float(pair_data['txCount']),
                "volumeToken1": float(pair_data['volumeToken1']),
                
            }
        else:
            return {
                "reserveUSD": 0,
                "reserve0": 0,
                "reserve1": 0,
                "txCount": 0,
                "volumeToken1":0,
            } 
            
        #print("No pair details found for the given pair ID.")

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"An error occurred while making the request: {req_err}")
    except ValueError as val_err:
        print(f"Value error while parsing data: {val_err}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return 0,0,0


def get_liquidity_pair_address(token_address):
    """
    Fetch the liquidity pair address, derived ETH price, and token decimals for a given token address.
    Returns default values in case of an error or missing data to safely continue execution.
    """
    try:
        # GraphQL query to get token details
        query = """
        query {
          token(id: "%s") {
            derivedETH
            pairBase(first: 1) {
              id
            }
          }
        }
        """ % token_address.lower()

        # Make the API request
        response = requests.post(GRAPHQL_URL, json={'query': query}, timeout=10)
        response.raise_for_status()  # Raise an error for bad status codes

        # Parse the response JSON data
        data = response.json()
        # Check if the necessary 'token' data is available in the response
        if 'data' in data and 'token' in data['data'] and data['data']['token'] is not None:
            token_data = data['data']['token']
            # Extract derived ETH, decimals, and pair ID safely
            derived_eth = float(token_data.get('derivedETH', 0.0))  # Default to 0.0 if not present
            pair_ids = [pair['id'] for pair in token_data.get('pairBase', [])]

            if pair_ids:
                # Successfully retrieved all required data
                #print(f"Price in ETH: {derived_eth}")
                return derived_eth, pair_ids[0],
            else:
                #print("No pairBase ID found for this token.")
                return derived_eth, None
        else:
            # Handle case where the token data is not present in the response
            print("Token data not found in the response. The token might not be indexed yet.")
            derived_eth=0
            return derived_eth, None

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"An error occurred while making the request: {req_err}")
    except ValueError as val_err:
        print(f"Value error while parsing data: {val_err}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    # Return None values if any exception was caught or data was missing
    return None, None
