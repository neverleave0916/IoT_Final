# IoT_Final - 遠端農業監控平台
 110教育機器人與物聯網 期末專案

## 安裝
- python>=3.x
- Node-RED
```bash
npm install -g node-red
```
- Node-RED Dashboard
```bash
npm install -g node-red-dashboard
```
## 啟動
### Raspberry Pi主程式
- 啟動主程式
```python
python final.py
```
### 網頁端
- 啟動Node-RED
```
node-red
```
- 匯入flows.json至Node-RED
- 部署Node-RED
### 行動端
- 安裝MQTT Dashboard
  - https://play.google.com/store/apps/details?id=com.app.vetru.mqttdashboard&hl=zh_TW&gl=US
- 匯入備份
  - MqttDashBackup_1654660007987.mqttdash

## 畫面
- Node-RED Dashboard
<img src="https://user-images.githubusercontent.com/52253495/172526033-cf4ba36a-04e4-4326-94fb-b22fa2f35950.png" width="500">

- MQTT Dashboard
<img src="https://user-images.githubusercontent.com/52253495/172526116-f2fee68e-3e38-4631-904d-2ecb5dd94df0.jpg" width="200">
