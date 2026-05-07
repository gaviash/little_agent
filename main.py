from Agent import start,query
#from tools import shell
import asyncio

async def main():
    agent,memory = start()
    while True:
        message = input(">>> ")
        print(await query(agent,memory,message))

asyncio.run(main())
