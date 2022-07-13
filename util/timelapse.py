import datetime
import os
import pickle
import queue
import threading
import time
import subprocess

import boto3

UBV2H264_DIR = "/mnt/data_ext/shoe/"
UBV2H264_PATH = os.path.join(UBV2H264_DIR, "ubv2h264")
UBNT_UBVINFO_PATH = "/var/lib/containers/storage/overlay/703c602a2336017d614b24825a31d4763280ae3856497d28b7dc241f637f5869/diff/usr/share/unifi-protect/app/node_modules/.bin/ubnt_ubvinfo"
def UTC_OFFSET(t):
    spring_forward = datetime.datetime(2022, 3, 13)
    return datetime.timedelta(hours=(-8 if t < spring_forward else -7))
# duration in seconds. time lapses will span the time range (now - DURATION, now).
DURATION = 10 * 3600
# # of timelapses to encode in parallel
WORKER_COUNT = 3
# bitrates: list of integer, kbps
# retimings: list of integer, 20 == 20x speedup
CAMERAS = {
    "E063DA008079" : {"bitrates" : [2000, 9000], "retimings" : [50, 250, 500]},
    "E063DA008019" : {"bitrates" : [2000, 9000], "retimings" : [50, 250, 500]},
    "E063DA005DDC" : {"bitrates" : [4000, 16000], "retimings" : [50, 250, 500]},
    "68D79AE13477" : {"bitrates" : [4000, 16000], "retimings" : [50, 250, 500]},
    "E063DA00801D" : {"bitrates" : [2000, 9000], "retimings" : [50, 250, 500]},
}
#CAMERAS = {
#    "E063DA008079" : {"bitrate" : 9000, "retimings" : [10]},
#    "E063DA008019" : {"bitrate" : 9000, "retimings" : [10]},
#    "E063DA005DDC" : {"bitrate" : 16000, "retimings" : [10]},
#    "E063DA00801D" : {"bitrate" : 9000, "retimings" : [10]},
#}
S3_BUCKET = open("s3_bucket").read().strip()
# udm does not allow ssh keys :-/
SSH_PASS = open("ssh_pass").read().strip()

def gen_worker(q, target):
    while True:
        task = q.get()
        if task is None:
            break

        target(task)

def start_workers(count, q, target):
    result = [threading.Thread(target=gen_worker, args=(q, target)) for _ in range(count)]
    for thread in result:
        thread.start()
    return result

def stop_workers(workers, q):
    # stop the workers
    for _ in workers:
        q.put(None)

    # wait for workers to exit
    for w in workers:
        w.join()

extraction_queue = queue.Queue()
encoding_queue = queue.Queue()
upload_queue = queue.Queue()

def extraction_worker(task):
    cam, start_time, duration = task
    end_time = start_time + datetime.timedelta(seconds=duration)
    start_time_local = start_time + UTC_OFFSET(start_time)
    ts = int(time.mktime(start_time.timetuple()) * 1000)
    te = int(time.mktime(end_time.timetuple()) * 1000)
    args = ["sshpass", f"-p\"{SSH_PASS}\"", "ssh", "root@192.168.1.1", UBV2H264_PATH, UBNT_UBVINFO_PATH, cam,
            f"{start_time_local.year}", f"{start_time_local.month:02}", f"{start_time_local.day:02}",
            f"{ts}", f"{te}"]
    # print(' '.join(args))
    subprocess.run(" ".join(args), shell=True)

    # copy the h264 back here
    subprocess.run(" ".join(["sshpass", f"-p\"{SSH_PASS}\"", "scp", os.path.join(f"root@192.168.1.1:{UBV2H264_DIR}", cam + ".h264"), "."]), shell=True)

    for bitrate in CAMERAS[cam]["bitrates"]:
        for retiming in CAMERAS[cam]["retimings"]:
            encoding_queue.put((cam, start_time, bitrate, retiming))

def encoding_worker(task):
    cam, start_time, bitrate, retiming = task
    input_filename = cam + ".h264"
    output_filename = cam + f"_{retiming}x_{bitrate//1000}Mbps" + ".mp4"
    #subprocess.run(["ffmpeg", "-y", "-i", input_filename, "-c:v", "copy",
    #    output_filename])
    subprocess.run(["ffmpeg", "-y", "-i", input_filename, "-filter:v",
        f"setpts={1/retiming:0.04f}*PTS",
        "-b:v", f"{bitrate}K", "-maxrate", f"{bitrate}K", "-bufsize", f"{bitrate*2}K",
        output_filename])
    upload_queue.put((output_filename, start_time))

def upload_worker(task):
    filename, t = task
    t = t + UTC_OFFSET(t)
    s3 = boto3.resource("s3")
    print(f"Starting to upload {filename}")
    s3.meta.client.upload_file(filename, S3_BUCKET, f"{t.year}/{t.month:02}/{t.day:02}/{filename}")
    print(f"Completed uploading {filename}")

def copy_ubv2h264():
    subprocess.run(" ".join(["sshpass", f"-p\"{SSH_PASS}\"", "scp", "../build/ubv2h264", f"root@192.168.1.1:{UBV2H264_PATH}"]), shell=True)

def main():
    copy_ubv2h264()

    # i/o perf suffers badly with >1 extraction worker. it's better to get one video
    # extracted and copied over quickly to start the encoding workers.
    extraction_workers = start_workers(1, extraction_queue, extraction_worker)
    encoding_workers = start_workers(WORKER_COUNT, encoding_queue, encoding_worker)
    upload_workers = start_workers(8, upload_queue, upload_worker)

    now_time = datetime.datetime.now()
    with open('next_dt', 'rb') as dtf:
        now_time = pickle.loads(dtf.read())
    # now_time = datetime.datetime(2022, 6, 4, 1, 0, 0, 0)
    while True:
        while now_time > datetime.datetime.now():
            time.sleep(5)
        print(f'Starting on {now_time}')
        start_time = now_time - datetime.timedelta(seconds=DURATION)
        for cam in CAMERAS.keys():
            extraction_queue.put((cam, start_time, DURATION))
        while not extraction_queue.empty():
            time.sleep(5)
        while not encoding_queue.empty():
            time.sleep(5)
        now_time = now_time + datetime.timedelta(days=1)
        with open('next_dt', 'wb') as dtf:
            dtf.write(pickle.dumps(now_time))

    stop_workers(extraction_workers, extraction_queue)
    stop_workers(encoding_workers, encoding_queue)
    stop_workers(upload_workers, upload_queue)

if __name__ == '__main__':
    main()
