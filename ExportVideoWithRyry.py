import os, json, re, shutil
from ryry import server_func
from ryry import ryry_widget

def export(config, output_dir):
    config["output"] = output_dir
    if os.path.exists(output_dir) == False:
        os.makedirs(output_dir)
    ryry_widget.installWidget("GenVideo_Template2")
    data = server_func.Task("GenVideo_Template2", [
        {
            "params": config,
            "task_id": config["ftp_folder_name"]
        }
    ]).call()
    if len(data[0].get("url", "")) > 0:
        result_file = os.path.join(output_dir, "new.mp4")
        if os.path.exists(result_file):
            def get_next_video_filename(folder_path):
                pattern = re.compile(r'result_(\d+)\.mp4')
                files = os.listdir(folder_path)
                ids = []
                for file in files:
                    match = pattern.match(file)
                    if match:
                        ids.append(int(match.group(1)))
                if not ids:
                    return 'result_1.mp4'
                next_id = max(ids) + 1
                return f'result_{next_id}.mp4'
            shutil.copyfile(result_file, os.path.join(output_dir, get_next_video_filename(output_dir)))
            os.remove(result_file)
            print("export video success.")
        else:
            print("export video success, but video not found!")
    else:
        print("export video fail !")
        print(data)