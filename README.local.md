## (local)本地環境隔離快速專案部屬(隨機PORT) + Postman-collection(newman)自動測試
需安裝Docker, 若在Linux環境需額外手動安裝docker-compose, 部屬結果與UI相同
``` 
docker-compose up -d --build 
```
部屬包含flask網頁 + Postman-collection(newman)自動測試, 自動測試報告結果會自動產生在`app/newman-report.xml`, 驗證後即可上傳程式碼
### 查看部屬結果 `docker-compose ps`
```
                   Name                                  Command               State             Ports
---------------------------------------------------------------------------------------------------------------
docker-flask-webpage-1_postman_collection_1   newman run /etc/postman/po ...   Exit 0
docker-flask-webpage-1_web_1                  /bin/sh -c python3 -u main.py    Up       0.0.0.0:49196->5000/tcp
```
訊息內有顯示`0.0.0.0:49196`，則代表可透過 http://localhost:49196 或是 http://您主機IP:49196 來連線到本地部屬的網站
### 查看與追蹤部屬的網頁伺服器紀錄Log `docker-compose logs -f web`
可用`Ctrl+V`來離開Log追蹤
```
web_1                 |  * Serving Flask app "main" (lazy loading)
web_1                 |  * Environment: production
web_1                 |    WARNING: This is a development server. Do not use it in a production deployment.
web_1                 |    Use a production WSGI server instead.
web_1                 |  * Debug mode: on
web_1                 |  * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
web_1                 |  * Restarting with stat
web_1                 |  * Debugger is active!
web_1                 |  * Debugger PIN: 196-195-249
web_1                 | 172.21.0.3 - - [08/Mar/2021 03:38:29] "GET / HTTP/1.1" 200 -
web_1                 | 10.212.134.104 - - [08/Mar/2021 03:58:23] "GET / HTTP/1.1" 200 -
web_1                 | 10.212.134.104 - - [08/Mar/2021 03:58:23] "GET /static/css/template.css HTTP/1.1" 200 -
web_1                 | 10.212.134.104 - - [08/Mar/2021 03:58:23] "GET /favicon.ico HTTP/1.1" 404 -
web_1                 | 10.212.134.104 - - [08/Mar/2021 03:58:25] "GET /about HTTP/1.1" 200 -
```
### 查看(local)Postman-collection(newman)自動測試以及報告文件
當執行本地環境快速專案部屬時，會自動將您的網站與資料庫部屬完成後再進行自動測試
* 自動測試的檔案在`app/postman_collection_local.json` 使用者可以按照開發上的需求去進行修改
:warning: 
```
  若您是在本地環境直接開發的話，可能會透過瀏覽器連http://localhost:5000
  而到了json檔案內就將http://localhost:5000改成http://web:5000即可
```
自動測試報告結果會自動產生在`app`資料夾內的`newman-report.xml`

## Flask 
### function:
* `url_for()`. It accepts the name of the function as an argument
### folder:
* `templates`: html template file
* `static`: css and image file
