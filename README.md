# ubv2h264
Extract h264 streams from Ubiquiti Unifi Protect ubv files

## Background
Unifi's ubv files contain multiple video and audio tracks, along
with some inline metadata. The ubnt_ubvinfo binary can parse ubv
files and print out information about their contents. This ubv2h264
utility calls ubnt_ubvinfo to find video payloads and extracts them into a
file that contains a valid h264 stream. This stream can then easily
be processed by e.g. ffmpeg to e.g. put it in an mp4 container.
The location of the ubnt_ubvinfo binary can change, so this utility
takes the path to ubnt_ubvinfo as an argument.
Other arguments include the camera ID (which is the prefix on the
ubv filenames), and the day and time range you wish to extract.

## Building
The build requires the aarch64-linux-gnu toolchain. On Ubuntu,
this command should install the toolchain.

    # apt install g++-aarch64-linux-gnu

After that, simply running `make` will build the ubv2h264 binary.

    $ make

The binary can then be copied to your Protect server and run.

## Examples

Extracting 2 hours from camera E063DA005DDC on 4/8/2021, starting at 10:30am.

    $ ubv2h264 \
    /var/lib/containers/storage/overlay/ca9d903300a70452a2a2a8e1a1830ac0bab10fbcaf3c576398fd53755c279814/diff/usr/share/unifi-protect/app/node_modules/.bin/ubnt_ubvinfo \
    E063DA005DDC 2021 04 08 1617903000000 1617910200000

Putting the resulting h264 stream into an mp4 container:

    $ ffmpeg -i video.h264 -c:v copy video.mp4

Creating a 50x speed time lapse mp4 from the h264 stream:

    $ ffmpeg -i video.h264 -filter:v "setpts=0.02*PTS" video.mp4

The print_args.py utility can be used to generate the date and time
arguments (the last 5 arguments to ubv2h264).
