FROM ros:humble-ros-base
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip python3-tk libgl1 libegl1 libglib2.0-0 libgl1-mesa-dri \
    mesa-utils xvfb xauth ros-humble-rviz2 ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-demo.txt /tmp/requirements-demo.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements-demo.txt
ENV PYTHONPATH=/evidence/src:/evidence/vendor/f1tenth_gym/gym:/evidence/vendor/metadrive
ENV PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/numba MPLCONFIGDIR=/tmp/matplotlib
ENV ROS_DOMAIN_ID=73 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
WORKDIR /lab
