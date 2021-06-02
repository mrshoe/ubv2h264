#include <algorithm>
#include <cassert>
#include <fstream>
#include <string>
#include <vector>

#include <arpa/inet.h>
#include <stdio.h>
#include <sys/types.h>
#include <dirent.h>

#include "spawn.hpp"

using std::string;
using std::vector;
using std::getline;
using std::cout;
using std::endl;

vector<string> find_files(string video_dir, string camera_id)
{
    vector<string> result;
    DIR* dir = opendir(video_dir.c_str());
    while (auto ent = readdir(dir))
    {
        string fn = ent->d_name;
        // The "<camera-id>_0_rotating_<timestamp>.ubv" files are full resolution
        // The "<camera-id>_2_rotating_<timestamp>.ubv" files are lower resolution
        if (fn.find(camera_id + "_0_") != string::npos)
        {
            result.push_back(fn);
        }
    }
    return result;
}

void process_file(string ubvinfo_path, string filename, uint64_t start_tstamp,
        uint64_t end_tstamp, std::ofstream& output)
{
    cout << "process_file: " << ubvinfo_path << " " << filename << endl;
    // Anecdotally, keyframes were all <500KB
    static constexpr size_t buf_size = 10 * 1024 * 1024;
    static char buffer[buf_size];
    // The video payloads in the ubv file consist of a bunch of (4 byte) length-prefixed
    // h264 frames. A valid h264 stream consists of sentinel-prefixed h264 frames
    // So, we read the length but we write out this sentinel instead.
    static char nal_sentinel[4] = {0, 0, 0, 1};
    std::ifstream input{filename};
    const char* const ubvinfo_argv[] = {
       ubvinfo_path.c_str(),
       "-f",
       filename.c_str(),
        (const char*)0
    };
    spawn ubvinfo(ubvinfo_argv);
    // Skip any non-keyframes before we see a keyframe, that way the output video
    // starts with a keyframe
    bool wrote_keyframe = false;
    int frames_written = 0;
    while (!ubvinfo.stdout.eof())
    {
        string line;
        getline(ubvinfo.stdout, line);
        char type[10];
        int offset;
        int size;
        int keyframe;
        uint64_t timestamp;
        int clock_rate;
        // Parse the output from ubnt_ubvinfo
        int matches = sscanf(line.c_str(), " %s %*s %d %d %d %*s %*s %lu %d",
        type, &keyframe, &offset, &size, &timestamp, &clock_rate);
        uint64_t epoch_time = timestamp / (clock_rate / 1000);
        if (matches == 6 && type[0] == 'V' && (wrote_keyframe || keyframe) &&
            epoch_time > start_tstamp && epoch_time < end_tstamp)
        {
            input.seekg(offset);
            int bytes_read = 0;
            while (bytes_read < size)
            {
                output.write(nal_sentinel, 4);
                int32_t nal_size = 0;
                input.read(reinterpret_cast<char*>(&nal_size), sizeof(nal_size));
                nal_size = htonl(nal_size);
                assert(nal_size <= buf_size);
                input.read(buffer, nal_size);
                output.write(buffer, nal_size);
                bytes_read += (sizeof(nal_size) + nal_size);
            }
            wrote_keyframe = true;
            frames_written++;
            cout << type << ", " << offset << ", " << size << " " << epoch_time << " " << frames_written << endl;
        }
    }
    cout << "Waiting to terminate..." << endl;
    cout << "Status: " << ubvinfo.wait() << endl;
}

int main(int argc, char** argv)
{
    if (argc != 8)
    {
        cout << "Usage:" << endl;
        cout << "\t" << argv[0] << " ubnt_ubvinfo-path camera-id year month day start-timestamp end-timestamp" << endl;
        cout << "\tubnt_ubvinfo-path: absolute path to ubnt_ubvinfo binary" << endl;
        cout << "\tcamera-id: ex. E063DA008079" << endl;
        cout << "\tyear: ex. 2021" << endl;
        cout << "\tmonth: 01-12" << endl;
        cout << "\tday: 01-31" << endl;
        cout << "\tstart-timestamp: milliseconds since 1970, local time" << endl;
        cout << "\tend-timestamp: milliseconds since 1970, local time" << endl;
        return 1;
    }

    string video_dir = "/mnt/data_ext/unifi-os/unifi-protect/video/";
    video_dir = video_dir + argv[3] + "/" + argv[4] + "/" + argv[5] + "/";
    cout << video_dir.c_str() << endl;
    auto files = find_files(video_dir, argv[2]);
    std::sort(files.begin(), files.end());

    uint64_t start_tstamp = std::stol(argv[6]);
    uint64_t end_tstamp = std::stol(argv[7]);
    std::ofstream output{"/mnt/data_ext/shoe/video.h264"};
    for (auto& f : files)
    {
        process_file(argv[1], video_dir + f, start_tstamp, end_tstamp, output);
    }
    return 0;
}
