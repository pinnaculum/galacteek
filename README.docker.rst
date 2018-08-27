Docker image
------------

A demo Docker image (unmaintained) is on the Gitlab's registry:

.. code-block:: shell

    docker pull registry.gitlab.com/galacteek/galacteek:latest
    docker run -e DISPLAY=$DISPLAY -e QTWEBENGINE_DISABLE_SANDBOX=1 -v /tmp/.X11-unix:/tmp/.X11-unix registry.gitlab.com/galacteek/galacteek

Be sure to have proper permissions to the X server. If you get a
*connection refused* message, just run *xhost +*.
