
import json
import os

# スケジュールファイルの読み込み
data_dir = os.path.join(os.getcwd(), "data")
scheduled_file = os.path.join(data_dir, "scheduled.json")

if os.path.exists(scheduled_file):
    with open(scheduled_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # pending以外の投稿（postedなど）は残す
    new_data = [item for item in data if item["status"] != "pending"]
    old_pending_count = len(data) - len(new_data)
    
    with open(scheduled_file, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"待機中のツイート {old_pending_count} 件を削除しました。")
else:
    print("スケジュールファイルが見つかりません。")
