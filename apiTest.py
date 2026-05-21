import requests

def getBitcoinPrice():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    print("正在向服务器发送请求，请稍候...")

    response = requests.get(url) #only fetch data do not change data

    #check server stats
    if response.status_code == 200:
        print("请求成功！(Status Code: 200)")

        data = response.json() #translate server reply into python language

        print(f"服务器返回的原始 JSON 数据: {data}") #print out how does the data structure looks like

        btc_price = data['bitcoin']['usd'] #get what we need
        print(f"\n目前比特币的实时价格是: ${btc_price} USD")

    else:
        print(f"哎呀，请求失败了！错误码: {response.status_code}")

if  __name__ == "__main__":
    getBitcoinPrice()


