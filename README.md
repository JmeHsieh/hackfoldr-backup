# hackfoldr-backup
Backup csv sources in json format for http://beta.hackfoldr.org

# 使用限制
由於 hackfoldrs 資訊是從 [g0v-data/hackpad-backup-g0v](https://github.com/g0v-data/hackpad-backup-g0v) 備份中掃描並整理出來，因此目前僅適用於 g0v 的 hackfoldrs。若有自己的 hackpad-backup repo，可在 config.json 中修改 `hackpad_repo_url` 以指定 hackpads 來源</br>

# 如何開始
目前 config.json 設定將資料備份到： [jmehsieh/hackfoldr-backup-g0v](https://github.com/jmehsieh/hackfoldr-backup-g0v)</br>
使用者可自行設定備份到其他 github 帳號下：</br>
## 
1. 建立一個 repo
2. 將 config.json 中 `hackfoldr_repo_url` 指定為方才建立 repo 的 url 即可

# 環境
1. Git
2. Python 3.5.2
3. Virtualenv

# 開始使用
```
# 建立 virtualenv
$ virtualenv venv
$ pip install -r requirements.txt
$ source venv/bin/activate

# 執行
$ python3 backup.py
```

# 程式流程
1. 根據 config.json clone (or pull) `hackpad_repo_url`
2. 根據 config.json clone (or pull) `hackfoldr_repo_url`
3. 掃描 hackpad_repo 中的 html 文件，取得所有 hackfoldr 資訊
4. 根據 hackfoldr_id 去 ethercalc or google spreadsheets 取得 csv
5. 將更新的 hackfoldrs 複製到 hackfoldr_repo 並 commit & push
6. 全部流程約 4 mins
