from Agent import start,query
#from tools import shell
import asyncio

async def main():
    agent,memory = start()
    while True:
        message = input(">>> ")
        response = await query(agent,memory,message)
        print("\n\n [REPONSE]")
        print(response)

asyncio.run(main())
