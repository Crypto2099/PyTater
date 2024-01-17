import hashlib
import httpx
import json
import os

from colors import random_color
from dotenv import load_dotenv
from time import sleep


load_dotenv()

miner_id = os.getenv('miner_id')
all_miners = [miner_id]







def get_status(miner_id):
    try:
        response = httpx.get(f'https://starch.one/api/miner/{miner_id}', timeout=10)
    except:
        print("Could not fetch status")
        return None, None
    try:
        payload = response.json()
    except:
        print("Could not decode status")
        return None, None
    try:
        starch_balance = payload['balance']
        block_count = payload['blocks']
        return starch_balance, block_count
    except:
        return None, None

def get_pending():
    try:
        res = httpx.get('https://starch.one/api/pending_blocks', timeout=10)
    except:
        print("Could not fetch pending!")
        return []
    try:
        response = res.json()
    except json.decoder.JSONDecodeError:
        print(f"Could not decode pending!")
        return []
    if len(response.get('pending_blocks', [])) != 0:
        pending_blocks = response['pending_blocks']
        return pending_blocks
    else:
        return []

def get_miner_blocks(miner_id, pending_blocks):
    miner_block, miner_block_hash = None, None
    for block in pending_blocks:
        if block['miner_id'] == miner_id:
            miner_block = block
            miner_block_hash = block['previous_hash']
            break
    return miner_block, miner_block_hash



def mine_block(miner_block, last_block_hash):
    print("Unearthing $STRCH treasures with potato prowess... Mining spudtastic crypto gold.")
    if miner_block == None or last_block_hash == None:
    #if miner_block['previous_hash'] == last_block_hash:
        print(f"My Last Block: (Hash: {last_own_block['previous_hash']}, Color: {last_own_block['color']})")
        print("We should mine a block!")
        new_block = solve(last_block_hash)
        submit_block(new_block)


def get_chain_config(block_height):
    last_block, last_block_hash = None, None
    # logging.info("Getting chain config...")
    try:
        res = httpx.get('https://starch.one/api/blockchain_config', timeout=10)
    except:
        # 15639bc8e9...974951272c
        print("Could not fetch configuration!")
        return block_height, last_block, last_block_hash
    try:
        response = res.json()
    except:
        print("Could not decode configuration!")
        return block_height, None, None
    try:
        if response['blockchain_size'] > block_height:
            block_height = response['blockchain_size']
            last_block = response['last_block']
            last_block_hash = last_block['hash']
            return block_height, last_block, last_block_hash
    except:
        return block_height, last_block, last_block_hash

def solve(last_block_hash, miner_id):
    color = random_color(miner_id, last_block_hash)
    print(f"Solving New Block:\nHash: {last_block_hash}\nMiner ID: {miner_id}\nColor: {color}")
    solution = last_block_hash + " " + miner_id + " " + color
    m = hashlib.sha256()
    m.update(bytes(solution, 'ascii'))
    new_hash = m.hexdigest()
    print(f"Block hash: {new_hash}")
    return {'hash': new_hash, 'color': color, 'miner_id': miner_id}

def submit_block(new_block):
    try:
        resp = httpx.post('https://starch.one/api/submit_block', json=new_block, timeout=10)
    except:
        print("Could not submit block?!")
        return
    print("New block submitted to the chain!")

def run_miner():
    global block_height, miner_block, miner_block_hash
    block_height = 0
    starch_balance, block_count = get_status(miner_id)
    while True:
        if block_height != 0:
            print(f'block height: {block_height}')
        current_block_height, current_block, current_block_hash = get_chain_config(block_height)
        if current_block_height > block_height:
            block_height = current_block_height
            new_block = solve(current_block_hash, miner_id)
            submit_block(new_block)
            pending_blocks = get_pending()
            miner_block, miner_block_hash = get_miner_blocks(miner_id, pending_blocks)
        sleep(45)

run_miner()