# Sumo Control
**Update:** I'm having to work on a different project for my master's so this will be indefinitely suspended. I hope to return to it in future.

My plan is to train a Jumping Sumo minidrone from Parrot to navigate a track using reinforcement learning. This project will be divided into several stages:

- [x] Implement the ARSDK3 protocol in python to allow me control the drone directly via a PC and stream video as well
- [X] Implement FAST RCNN Object Detection with Tensorflow-NEW
- [X] Add Jump and load command -NEW
- [X] Add auto-driving feature with object detection


## Requirements
More requirements will be added as the project progresses.

### Software
- Python 3
- OpenCV
- Tensorflow

### Hardware
- One Jumping Sumo (I am using a Jumping Race Max, other Jumping Drones should also work)
- Several batteries :weary:

## Miscellaneous
- I was able to install OpenCV 3 in my conda environment using: `conda install -c menpo opencv3`
- The minidrone module was adapted from [forthtemple/py-faster-rcnn](https://github.com/forthtemple/py-faster-rcnn) and [haraisao/JumpingSumo-Python
](https://github.com/haraisao/JumpingSumo-Python). As I am only interested in ground motion, I have limited my implementation to that (no jumping, ...)
- The Parrot ARSDK3 document can be found [here](http://developer.parrot.com/docs/bebop/ARSDK_Protocols.pdf). I was also able to find some useful information on their [GitHub](https://github.com/Parrot-Developers) page.
