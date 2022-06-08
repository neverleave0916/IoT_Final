import pymysql
import datetime
import RPi.GPIO as GPIO
import time
import paho.mqtt.client as mqtt
import pytz
import json
tw = pytz.timezone('Asia/Taipei')
import random

# ==============================================================
# 設定值
# ==============================================================
MQTT_SERVER = "IP"  
MQTT_PORT = 1883 
MQTT_ALIVE = 0  

DB_IP = "IP"
DB_USER = "robot"
DB_PASSWORD = "pwd"
DB_PORT = 3306

LIGHT_IO = 4
FAN_IO = 3
PUMP_IO = 2

DHT_IO = 14

IF_DHT_RAMDOM = True

# ==============================================================
# 函數
# ==============================================================
def reScale(OldValue, new_max=100):
    #OldRange = (OldMax - OldMin)
    OldRange = 1023
    if OldRange == 0:
        pass
    else:
        #NewRange = (NewMax - NewMin)
        NewRange = new_max
        #NewValue = (((OldValue - OldMin) * NewRange) / OldRange) + NewMin
        NewValue = OldValue * (NewRange / OldRange)
    return round(NewValue,2)

# ==============================================================
# 資料庫
# ==============================================================
def connectToDB(forum):
    db = pymysql.connect(host=DB_IP, user=DB_USER, password=DB_PASSWORD, port=DB_PORT, charset='utf8mb4')
    cursor = db.cursor()
    cursor.execute("use " + forum)  # 設定database
    return (cursor,db) 

cursor,db = connectToDB("IoT")

# ==============================================================
# 定義classes
# ==============================================================
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
class GPIOdevie:
    def __init__(self, GPIOnum, name = "", OUT_IN="OUT"):
        self.GPIOnum = GPIOnum
        self.name = name
        if OUT_IN == "OUT":
            GPIO.setup(GPIOnum, GPIO.OUT)
        else:
            GPIO.setup(GPIOnum, GPIO.IN)
    def setup(self, threshold=0, mode="g"):
        self.threshold = threshold
        self.mode = mode
    def turnOn(self):
        GPIO.output(self.GPIOnum, True)
    def turnOff(self):
        GPIO.output(self.GPIOnum, False)
        
class Relay(GPIOdevie):
    def __init__(self, GPIOnum, name="", mode="auto", threshold=0, status="off", trigger_mode = "greater", current_value = 0, High_trigger=True, OUT_IN="OUT"):
        super().__init__(GPIOnum, name, OUT_IN)
        self.High_trigger = High_trigger
        # Setting
        self.mode=mode                    # auto or manual
        self.threshold = threshold        # threshold
        self.status = status              # status of relay
        self.trigger_mode = trigger_mode  # trigger when greater than threshold or less than threshold
        # Default 0
        self.current_value = current_value
    def turnOn(self):
        GPIO.output(self.GPIOnum, True) if self.High_trigger else GPIO.output(self.GPIOnum, False)
    def turnOff(self):
        GPIO.output(self.GPIOnum, False) if self.High_trigger else GPIO.output(self.GPIOnum, True)

    def updateStatus(self):
        if self.mode == "manual":
            if self.status =="on":
                self.turnOn()
            elif self.status =="off":
                self.turnOff()
        elif self.mode == "auto":
            if self.trigger_mode =="greater":
                if self.current_value >= self.threshold:
                    self.status ="on"
                    self.turnOn()
                else:
                    self.status ="off"
                    self.turnOff()
            elif self.trigger_mode =="lesser":
                if self.current_value < self.threshold:
                    self.status ="on"
                    self.turnOn()
                else:
                    self.status ="off"
                    self.turnOff()
    def getStatusInt(self):
        if self.status =="on":
            return 1
        elif self.status =="off":
            return 0
    def getMode(self):
        if self.mode =="auto":
            return "auto"
        elif self.mode =="manual":
            return "manual"
    def getCurrentValue(self):
        return self.current_value
    def getThreshold(self):
        return self.threshold
    def updateCurrent(self, current_value):
        self.current_value = current_value
        self.updateStatus()
    def setStatus(self,s):
        if s == 1:
            self.status = "on"
        elif s==0:
            self.status = "off"
        self.updateStatus()
    def updateSetting(self, mode, threshold, status="off", trigger_mode="greater",current_value = None):
        self.mode=mode
        self.threshold = threshold
        self.status = status
        self.trigger_mode = trigger_mode
        if current_value is not None:
            self.current_value = current_value
        self.updateStatus()
    def updateSettingByDict(self, data):
        if "mode" in data:
            self.mode = data["mode"]
        if "threshold" in data:
            self.threshold = data["threshold"]
        if "status" in data:
            self.status = data["status"]
        if "trigger_mode" in data:
            self.trigger_mode = data["trigger_mode"]
        if "value" in data:
            self.current_value = data["value"]
        self.updateStatus()
        
    
# ==============================================================
# 宣告感測器與設備
# ==============================================================
#rLED = GPIOdevie(4,"OUT")
#yLED = GPIOdevie(3,"OUT")
#gLED = GPIOdevie(2,"OUT")

#rLED.turnOff()
#yLED.turnOff()
#gLED.turnOff()

# init device
# 17 27 22
light = Relay(LIGHT_IO, name = "light", mode="auto", threshold=500, status="off", trigger_mode = "lesser", current_value = 0, High_trigger=True)
fan = Relay(FAN_IO, name = "fan", mode="auto", threshold=500, status="off", trigger_mode = "greater", current_value = 0, High_trigger=True)
pump = Relay(PUMP_IO, name = "pump", mode="auto", threshold=500, status="off", trigger_mode = "lesser", current_value = 0, High_trigger=True)

devices = [{
                "topic" : "/Farm/Device/Light",
                "device" : light
            },{
                "topic" : "/Farm/Device/Fan",
                "device":fan
            },{
                "topic" : "/Farm/Device/Pump",
                "device":pump
            }            
]

sensor_topics = {
    "topic_tem" : "/Farm/Sensor/Temperature",
    "topic_hum" : "/Farm/Sensor/Humidity",
    "topic_light" : "/Farm/Sensor/Light",
    "topic_soil" : "/Farm/Sensor/SoilHumidity",
    "topic_water" : "/Farm/Sensor/WaterLevel"
}

# ==============================================================
# subscript端程式
# ==============================================================

# 當地端程式連線伺服器得到回應時，要做的動作
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    # 將訂閱主題寫在on_connet中
    # 如果我們失去連線或重新連線時 
    # 地端程式將會重新訂閱
    for value in sensor_topics.values():
        client.subscribe(value)
    for device in devices:
        client.subscribe(device['topic'])
        
# 當接收到從伺服器發送的訊息時要進行的動作
def on_message(client, userdata, msg):
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(tw)
    #now = tw.localize(now)
    # 轉換編碼utf-8才看得懂中文
    print(msg.topic+" "+ msg.payload.decode('utf-8'))

    # if device
    device_index = next((index for (index, device) in enumerate(devices) if device["topic"] == msg.topic), None)
    #elif msg.topic in [device["topic"] for device in devices]:
    if device_index is not None:
        data = json.loads(msg.payload.decode('utf-8'))
        print("update")
        if type(data) is int:
            devices[device_index]['device'].setStatus(data)
            payload = {"current_status": devices[device_index]['device'].getStatusInt(), "current_mode" : devices[device_index]['device'].getMode()}
            client.publish(devices[device_index]['topic'], json.dumps(payload), qos=1)
        elif type(data) is str:
            devices[device_index]['device'].updateSettingByDict({"mode":data})
            payload = {"current_status": devices[device_index]['device'].getStatusInt(), "current_mode" : devices[device_index]['device'].getMode()}
            client.publish(devices[device_index]['topic'], json.dumps(payload), qos=1)
        else:
            devices[device_index]['device'].updateSettingByDict(data)
        



    

    

# 連線設定
# 初始化地端程式
client = mqtt.Client()

# 設定連線的動作
client.on_connect = on_connect

# 設定接收訊息的動作
client.on_message = on_message

# 設定登入帳號密碼
#client.username_pw_set("try","xxxx")

# 設定連線資訊(IP, Port, 連線時間)
client.connect(MQTT_SERVER, MQTT_PORT, MQTT_ALIVE)

# 開始連線，執行設定的動作和處理重新連線問題
# 也可以手動使用其他loop函式來進行連接
# client.loop_forever()
client.loop_start()


# ==============================================================
# publish端程式
# ==============================================================
import Adafruit_DHT
from gpiozero import MCP3008

light_sensor = MCP3008(0)
soil_sensor = MCP3008(1)
water_sensor = MCP3008(2)

mqttc_public = mqtt.Client("M104020019_public")

mqttc_public.connect(MQTT_SERVER, MQTT_PORT, MQTT_ALIVE) 


mqttc_public.loop_start()
# *********************************************************************
# init device
# *********************************************************************
payload = {"mode":"auto", "threshold":500, "status": "on", "trigger_mode": "lesser"}
mqttc_public.publish("/Farm/Device/Light", json.dumps(payload), qos=1)

payload = {"mode":"auto", "threshold":33, "status": "on", "trigger_mode": "greater"}
mqttc_public.publish("/Farm/Device/Fan", json.dumps(payload), qos=1)

payload = {"mode":"auto", "threshold":100, "status": "on", "trigger_mode": "lesser"}
mqttc_public.publish("/Farm/Device/Pump", json.dumps(payload), qos=1)

while True:
    try:
        # *********************************************************************
        # Get sensor data
        # *********************************************************************
        if IF_DHT_RAMDOM:
            humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, DHT_IO)
            temperature_value = temperature
            humidity_value = humidity
        else:
            temperature_value = random.randint(25,40)
            humidity_value = random.randint(0,100)
        
        light_value = 1023 - light_sensor.raw_value
        soil_value = reScale(1023 - soil_sensor.raw_value)
        water_value = reScale(water_sensor.raw_value,5)
        #soil_value = random.randint(0,100)
        #water_value = round(random.uniform(0,5),2)
        #soil_value = soil_sensor.raw_value
        #water_value = water_sensor.raw_value

        # *********************************************************************
        # print sensor data
        # *********************************************************************
        print("temperature: "+str(temperature_value)+" humidity: "+str(humidity_value))
        
        # *********************************************************************
        # Publish sensor data TODO: if not None
        # *********************************************************************
        mqttc_public.publish("/Farm/Sensor/Temperature", temperature_value, qos=1)
        mqttc_public.publish("/Farm/Sensor/Humidity", humidity_value, qos=1)
        mqttc_public.publish("/Farm/Sensor/Light", light_value, qos=1)
        mqttc_public.publish("/Farm/Sensor/SoilHumidity", soil_value, qos=1)
        mqttc_public.publish("/Farm/Sensor/WaterLevel", water_value, qos=1)
        
        # *********************************************************************
        # Update device
        # *********************************************************************
        #payload = {"value": light_value}
        #mqttc_public.publish("/Farm/Device/Light", json.dumps(payload), qos=1)
        #payload = {"value": temperature_value}
        #mqttc_public.publish("/Farm/Device/Fan", json.dumps(payload), qos=1)
        #payload = {"value": soil_value}
        #mqttc_public.publish("/Farm/Device/Pump", json.dumps(payload), qos=1)
        
        # *********************************************************************
        # Update device value
        # *********************************************************************
        payload = {"value": light_value}
        light.updateSettingByDict(payload)
        #mqttc_public.publish("/Farm/Device/Light", json.dumps(payload), qos=1)
        payload = {"value": temperature_value}
        fan.updateSettingByDict(payload)
        #mqttc_public.publish("/Farm/Device/Fan", json.dumps(payload), qos=1)
        payload = {"value": soil_value}
        pump.updateSettingByDict(payload)
        #mqttc_public.publish("/Farm/Device/Pump", json.dumps(payload), qos=1)
        
        # *********************************************************************
        # Update device status and mode
        # *********************************************************************
        payload = {"current_status": light.getStatusInt(), "current_mode" : light.getMode()}
        mqttc_public.publish("/Farm/Device/Light", json.dumps(payload), qos=1)
        payload = {"current_status": fan.getStatusInt(), "current_mode" : fan.getMode()}
        mqttc_public.publish("/Farm/Device/Fan", json.dumps(payload), qos=1)
        payload = {"current_status": pump.getStatusInt(), "current_mode" : pump.getMode()}
        mqttc_public.publish("/Farm/Device/Pump", json.dumps(payload), qos=1)
        
        
        # *********************************************************************
        # Insert to database
        # *********************************************************************
        #now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(tw)
        #insert_data = [(now, "temperature", temperature_value),\
        #               (now, "humidity", humidity_value),\
        #               (now, "light", light_value),\
        #               (now, "soil", soil_value),\
        #               (now, "water", water_value)]
        # 輸入進資料庫
        #insert_sql = "INSERT INTO "+ "final" + " (time,sensor,value) VALUES (%s,%s,%s)"
        
        #try:
        #    cursor.executemany(insert_sql, insert_data)
        #    db.commit()
        #except Exception as e:
        #    print(e)
        #    db.rollback()
        
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(tw)
        insert_data = (now, temperature_value, humidity_value, light_value, soil_value, water_value)
        # 輸入進資料庫
        insert_sql = "INSERT INTO Final (time,temperature,humidity,light,soil,water) VALUES (%s,%s,%s,%s,%s,%s)"
        
        try:
            cursor.execute(insert_sql, insert_data)
            db.commit()
        except Exception as e:
            print(e)
            db.rollback()
    except Exception as e:
        print(e)
        print("notemp")
        
    #print(light_sensor.raw_value)
    #pump.updateCurrent(light_sensor.raw_value)
    time.sleep(5)
    
    

