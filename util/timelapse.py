import datetime
import os
import queue
import threading
import time
import subprocess

UBV2H264_DIR = "/mnt/data_ext/shoe/"
UBV2H264_PATH = os.path.join(UBV2H264_DIR, "ubv2h264")
UBNT_UBVINFO_PATH = "/var/lib/containers/storage/overlay/ca9d903300a70452a2a2a8e1a1830ac0bab10fbcaf3c576398fd53755c279814/diff/usr/share/unifi-protect/app/node_modules/.bin/ubnt_ubvinfo"
UTC_OFFSET = datetime.timedelta(hours=-7)
# duration in seconds. time lapses will span the time range (now - DURATION, now).
DURATION = 9 * 3600
# # of timelapses to encode in parallel
WORKER_COUNT = 2
# bitrate: integer, kbps
# retimings: list of integer, 20 == 20x speedup
CAMERAS = {
    "E063DA008079" : {"bitrate" : 9000, "retimings" : [10, 20]},
    "E063DA008019" : {"bitrate" : 9000, "retimings" : [10, 20]},
    "E063DA005DDC" : {"bitrate" : 16000, "retimings" : [10, 20]},
    "E063DA00801D" : {"bitrate" : 9000, "retimings" : [10, 20]},
}

def extraction_worker(q, encoding_queue):
    while True:
        task = q.get()
        if task is None:
            break

        cam, start_time, duration = task
        end_time = start_time + datetime.timedelta(seconds=duration)
        ts = int(time.mktime(start_time.timetuple()) * 1000)
        te = int(time.mktime(end_time.timetuple()) * 1000)
        args = ["ssh", "root@192.168.1.1", UBV2H264_PATH, UBNT_UBVINFO_PATH, cam,
                f"{start_time.year}", f"{start_time.month:02}", f"{start_time.day:02}",
                f"{ts}", f"{te}"]
        # print(' '.join(args))
        subprocess.run(args)

        # copy the h264 back here
        subprocess.run(["scp", os.path.join(f"root@192.168.1.1:{UBV2H264_DIR}", cam + ".h264"), "."])

        for retiming in CAMERAS[cam]["retimings"]:
            encoding_queue.put((cam, retiming))

def encoding_worker(q):
    while True:
        task = q.get()
        if task is None:
            break

        cam, retiming = task
        input_filename = cam + ".h264"
        output_filename = cam + f"_{retiming}x" + ".mp4"
        bitrate = CAMERAS[cam]["bitrate"]
        subprocess.run(["ffmpeg", "-y", "-i", input_filename, "-filter:v",
            f"setpts={1/retiming:0.02f}*PTS",
            "-b:v", f"{bitrate}K", "-maxrate", f"{bitrate}K", "-bufsize", f"{bitrate*2}K",
            output_filename])

def start_workers(count, target, args):
    result = [threading.Thread(target=target, args=args) for _ in range(count)]
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

def copy_ubv2h264():
    subprocess.run(["scp", "../build/ubv2h264", f"root@192.168.1.1:{UBV2H264_PATH}"])

def main():
    copy_ubv2h264()

    extraction_queue = queue.Queue()
    encoding_queue = queue.Queue()
    # i/o perf suffers badly with >1 extraction worker. it's better to get one video
    # extracted and copied over quickly to start the encoding workers.
    extraction_workers = start_workers(1, extraction_worker, (extraction_queue, encoding_queue))
    encoding_workers = start_workers(WORKER_COUNT, encoding_worker, (encoding_queue,))

    now_time = datetime.datetime.now()
    # now_time = datetime.datetime(year=2021, month=4, day=20, hour=14)
    start_time = now_time - UTC_OFFSET
    for cam in CAMERAS.keys():
        extraction_queue.put((cam, start_time, DURATION))

    stop_workers(extraction_workers, extraction_queue)
    stop_workers(encoding_workers, encoding_queue)

if __name__ == '__main__':
    main()
