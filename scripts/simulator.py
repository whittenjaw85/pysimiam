"""Simulator Thread

"""
import threading
from time import sleep, clock
from xmlparser import XMLParser

import khepera3
import pose
import simobject
from xmlparser import XMLParser
import pylygon

PAUSE = 0
RUN = 1

class Simulator(threading.Thread):

    def __init__(self, renderer, update_callback):
        """
        The viewer object supplies:
            a Renderer (viewer.renderer),
            a threading.Lock (viewer.lock) to lock painting
        and a threading.Event (viewer.event) to signal the end of painting
        """
        super(Simulator, self).__init__()

        #Attributes
        self.__stop = False
        self.__state = PAUSE
        self._renderer = renderer
        self.updateView = update_callback
        self.__center_on_robot = False

        # Zoom on scene - Move to read_config later
        self.__time_multiplier = 1.0
        self.__time = 0.0

        self._render_lock = threading.Lock()

        # Zoom on scene - Move to read_config later
        self._renderer.set_zoom_level(130)
        self._renderer.set_screen_pose(pose.Pose(-1.6,-1.5,0))

        # World objects
        self._robots = []
        self._obstacles = []

        #test code
#        self._robots = [ khepera3.Khepera3(pose.Pose(200.0, 250.0, 0.0)), ]
#        self._robots[0].set_wheel_speeds(18,16)
#        self._obstacles = [
#            simobject.Polygon(pose.Pose(200,200,0),[(-10,0),(0,-10),(10,0),(0,10)],0xFF0000),
#            simobject.Polygon(pose.Pose(300,100,0.1),[(-10,0),(0,-10),(10,0),(0,10)],0xFF0000),
#            simobject.Polygon(pose.Pose(100,300,0.4),[(-10,0),(0,-10),(10,0),(0,10)],0xFF0000)
#            ]
        #end test code
        self._world = None

    #def __delete__(self):
        #self.__state = PAUSE
        #self.__stop = True
        #self._render_lock.acquire()
        #self._render_lock.release()

    def read_config(self, config):
        ''' Read in the objects from the XML configuration file '''

        print 'reading initial configuration'
        parser = XMLParser(config)
        self._world = parser.parse()
        self.construct_world()

    def construct_world(self):
        if self._world is None:
            return

        self._render_lock.acquire()
        self._robots = []
        self._obstacles = []
        for thing in self._world:
            thing_type = thing[0]
            if thing_type == 'robot':
                robot_type, robot_pose  = thing[1], thing[2]
                if robot_type == 'khepera3.K3Supervisor':
                    self._robots.append(khepera3.Khepera3(pose.Pose(robot_pose)))
                else:
                    raise Exception('[Simulator.__init__] Unknown robot type!')
            elif thing_type == 'obstacle':
                obstacle_pose, obstacle_coords = thing[1], thing[2]
                self._obstacles.append(
                    simobject.Polygon(pose.Pose(obstacle_pose),
                                      obstacle_coords,
                                      0xFF0000))
            else:
                raise Exception('[Simulator.__init__] Unknown object: '
                                + str(thing_type))
        self._render_lock.release()
        self.__time = 0.0
        if self._robots == None:
            raise Exception('[Simulator.__init__] No robot specified!')
        else:
            self._robots[0].set_wheel_speeds(1.2,1.6)
            self.focus_on_world()
            self.draw()

    def run(self):
        print 'starting simulator thread'

        time_constant = 0.1  # 100 milliseconds
        self._render_lock.acquire()
        self._renderer.clear_screen() #create a white screen
        self.updateView()
        self._render_lock.release()

        #self.draw() # Draw at least once (Move to open afterwards)
        while not self.__stop:
            sleep(time_constant)
            if self.__state != RUN:
                continue
            for robot in self._robots:
                robot.move_to(robot.pose_after(time_constant))

            if self.check_collisions():
                print "Collision detected!"

                self.__stop = True

            if self.__state == RUN:
                current_clock = clock()
                elapsed_time = (current_clock - self.__clock)*self.__time_multiplier
                # Make sure we have at least 0.1 milliseconds,
                # otherwise numpy complains
                if elapsed_time < 0.0001:
                    continue
                self.__clock = current_clock
                self.__time += elapsed_time
                for robot in self._robots:
                    robot.move_to(robot.pose_after(elapsed_time))
                #if self.check_collisions():
                    #print "Collision detected!"
                    #self.__stop = True
            else:
                sleep(time_constant)

            # Draw to buffer-bitmap
            self.draw()

            # Draw to buffer-bitmap
            self.draw()


    def draw(self):
        self._render_lock.acquire()
        if self._robots and self.__center_on_robot:
            # Temporary fix - center onto first robot
            robot = self._robots[0]
            self._renderer.set_screen_center_pose(robot.get_pose())

        self._renderer.clear_screen()

        for obstacle in self._obstacles:
            obstacle.draw(self._renderer)

        # Draw the robots and sensors after obstacles
        for robot in self._robots:
            robot.draw(self._renderer)
            for s in robot.ir_sensors:
                s.draw(self._renderer)
        #end test code

        self.updateView()
        self._render_lock.release()

    def focus_on_world(self):
        self.__center_on_robot = False
        xl, yb, xr, yt = self._robots[0].get_bounds()
        for obstacle in self._obstacles:
            xlo, ybo, xro, yto = obstacle.get_bounds()
            if xlo < xl:
                xl = xlo
            if xro > xr:
                xr = xro
            if ybo < yb:
                yb = ybo
            if yto > yt:
                yt = yto
        self._render_lock.acquire()
        self._renderer.set_view_rect(xl,yb,xr-xl,yt-yb)
        self._render_lock.release()

    def focus_on_robot(self):
        self._render_lock.acquire()
        self.__center_on_robot = True
        self._render_lock.release()

    def show_grid(self, show=True):
        self._render_lock.acquire()
        self._renderer.show_grid(show)
        self._render_lock.release()
        if self._robots[0] is not None and self.__state != RUN:
            self.draw()

    def adjust_zoom(self,factor):
        self._render_lock.acquire()
        self._renderer.scale_zoom_level(factor)
        self._render_lock.release()

    # Stops the thread
    def stop(self):
        print 'stopping simulator thread'
        self.__stop = True

    def start_simulation(self):
        if self._robots:
            self.__clock = clock()
            self.__state = RUN

    def is_running(self):
        return self.__state == RUN

    def pause_simulation(self):
        self.__state = PAUSE

    def reset_simulation(self):
        self.pause_simulation()
        self.construct_world()

    def set_time_multiplier(self,multiplier):
        self.__time_multiplier = multiplier

    def get_time(self):
        return self.__time

    def check_collisions(self):
        poly_obstacles = []
        # prepare polygons for obstacles
        for obstacle in self._obstacles:
            poly = pylygon.Polygon(obstacle.get_world_envelope())
            poly_obstacles.append(poly)
            #print "Obstacle:", poly

        poly_robots = []
        # prepare polygons for robots
        for robot in self._robots:
            poly = pylygon.Polygon(robot.get_world_envelope())
            poly_robots.append(poly)
            #print "Robot:", poly

        checked_robots = []

        # check each robot's polygon
        for robot in poly_robots:
            # against obstacles
            for obstacle in poly_obstacles:
                collisions = robot.collidepoly(obstacle)
                # collidepoly returns False value or
                # an array of projections if found
                if isinstance(collisions,bool):
                    return True

            # against other robots
            for other in poly_robots:
                if other == robot: continue
                if other in checked_robots: continue
                collisions = robot.collidepoly(other)
                if isinstance(collisions,bool):
                    return True

            checked_robots.append(robot)
        return False

#end class Simulator
