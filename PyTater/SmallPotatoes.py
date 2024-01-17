import asyncio
import hashlib
import httpx
import json
import os
import random
import zlib


from datetime import datetime
from dotenv import load_dotenv


load_dotenv()

miner_id = os.getenv('miner_id')
print_run_total = False

class colors:
    FAIL = '\033[91m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    OKBLUE = '\033[94m'
    HEADER = '\033[95m'
    OKCYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

block_found = False
valid_miner = False

block_count = 0
block_height = 0
halving_count = 0
starch_balance = 0
starting_blocks = 0
# self.new_block_count = 0

last_block = None
last_block_hash = None
last_own_block = None
last_own_block_hash = None
pending_blocks = None

if miner_id == None:
    miner_id = input("Enter miner id to mine with: ")

run_start = datetime.now()



async def get_chain_config():
    global block_height, last_block, last_block_hash
    # logging.info("Getting chain config...")
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get('https://starch.one/api/blockchain_config', timeout=10)
    except:
        # 15639bc8e9...974951272c
        print("Could not fetch configuration!")
        return
    try:
        response = res.json()
    except json.decoder.JSONDecodeError:
        print("Could not decode configuration!")
        return
    try:
        block_height = response['blockchain_size']
        last_block = response['last_block']
        last_block_hash = last_block['hash']
    except:
        return


async def get_pending():
    global block_found, pending_blocks, last_own_block, last_own_block_hash
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get('https://starch.one/api/pending_blocks', timeout=10)
    except:
        print("Could not fetch pending!")
        return
    try:
        response = res.json()
    except json.decoder.JSONDecodeError:
        #print(res.status_code)
        print(f"Could not decode pending!")
        return
    try:
        #print(response)
        if response['pending_blocks']:
            block_found = False
            pending_blocks = response['pending_blocks']
            for block in pending_blocks:
                if block['miner_id'] == miner_id:
                    block_found = True
                    last_own_block = block
                    last_own_block_hash = block['previous_hash']
    except:
        return

async def get_status():
    global starch_balance, block_count, starting_blocks, valid_miner, miner_id
    if miner_id is None:
        return
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get('https://starch.one/api/miner/' + miner_id, timeout=10)
    except:
        print("Could not fetch status")
        return
    try:
        response = res.json()
    except:
        print("Could not decode status")
        return
    try:
        starch_balance = response['balance']
        block_count = response['blocks']
        if starting_blocks == 0 and response['blocks'] != 0:
            starting_blocks = response['blocks']
            # if self.block_count != self.starting_blocks:
            #     self.new_block_count = self.block_count - self.starting_blocks
            valid_miner = True
    except:
        valid_miner = False
        starting_blocks = 0
        block_count = 0
            # self.new_block_count = 0
        starch_balance = 0
        miner_id = None
        print('Miner ID not found')



async def mine_block():
    print("Unearthing $STRCH treasures with potato prowess... Mining spudtastic crypto gold.")
    await get_chain_config()
    if block_found and last_own_block['previous_hash'] == last_block['hash']:
        print(f"My Last Block: (Hash: {last_own_block['previous_hash']}, Color: {last_own_block['color']})")
        print("We should mine a block!")
        new_block = solve(last_block['hash'])
        await submit_block(new_block)


def solve(blockhash):
    color = randomColor(blockhash)
    print(f"Solving New Block:\nHash: {blockhash}\nMiner ID: {miner_id}\nColor: {color}")
    solution = blockhash + " " + miner_id + " " + color
    m = hashlib.sha256()
    m.update(bytes(solution, 'ascii'))
    new_hash = m.hexdigest()
    print(f"Block hash: {new_hash}")
    return {'hash': new_hash, 'color': color, 'miner_id': miner_id}

def randomColor(blockhash: str):
    seed = zlib.crc32(bytes(blockhash + miner_id, 'ascii'))
    random.seed(seed)
    random_number = random.randint(0, 16777215)
    hex_number = '{0:06X}'.format(random_number)
    return '#' + hex_number

async def submit_block(new_block):
    print(new_block)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post('https://starch.one/api/submit_block', json=new_block, timeout=10)
    except:
        print("Could not submit block?!")
        return
    print("New block submitted to the chain!")


async def run_miner():
    total_runs = 0
    while True:
        total_runs += 1
        await get_status()
        await get_pending()
        await mine_block()
        if print_run_total:
            print(f'Total Runs {total_runs}')
        await asyncio.sleep(30)

asyncio.run(run_miner())