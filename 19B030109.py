# pylint: disable=no-member
import pygame
from enum import Enum
import sys
import math
import pika
import uuid
import json
from threading import Thread
import random
import time


pygame.init()
pygame.font.init()
screen = pygame.display.set_mode((800, 600))

welcome = pygame.image.load('signs.png')

IP = '34.254.177.17'
PORT = 5672
VIRTUAL_HOST = 'dar-tanks'
USERNAME = 'dar-tanks'
PASSWORD = '5orPLExUYnyVYZg48caMpX'


font1 = pygame.font.SysFont("comicsansms", 20)


mainmenu = True
aimode = False


        

        

class TankRpcClient:
    def __init__(self):
        self.connection  = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=IP,                                                
                port=PORT,
                virtual_host=VIRTUAL_HOST,
                credentials=pika.PlainCredentials(
                    username=USERNAME,
                    password=PASSWORD
                )
            )
        )
        self.channel = self.connection.channel()                      
        queue = self.channel.queue_declare(queue='',exclusive=True,auto_delete=True) 
        self.callback_queue = queue.method.queue 
        self.channel.queue_bind(exchange='X:routing.topic',queue=self.callback_queue)
        self.channel.basic_consume(queue=self.callback_queue,
                                   on_message_callback=self.on_response,
                                   auto_ack=True) 
    
        self.response= None    
        self.corr_id = None
        self.token = None
        self.tank_id = None
        self.room_id = None

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = json.loads(body)
            print(self.response)

    def call(self, key, message={}):     
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='X:routing.topic',
            routing_key=key,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(message) 
        )
        while self.response is None:
            self.connection.process_data_events()

    def check_server_status(self): 
        self.call('tank.request.healthcheck')
        return self.response['status']== '200' 

    def obtain_token(self, room_id):
        
        message = {
            'roomId': room_id
        }
        self.call('tank.request.register', message)
        if 'token' in self.response:
            self.token = self.response['token']
            self.tank_id = self.response['tankId']
            self.room_id = self.response['roomId']
            return True
        return False

    def turn_tank(self, token, direction):
        message = {
            'token': token,
            'direction': direction
        }
        self.call('tank.request.turn', message)

    def fire_bullet(self, token):
        message = {
            'token': token
        }
        self.call('tank.request.fire', message)

class TankConsumerClient(Thread):

    def __init__(self, room_id):
        super().__init__()
        self.connection  = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=IP,                                                
                port=PORT,
                virtual_host=VIRTUAL_HOST,
                credentials=pika.PlainCredentials(
                    username=USERNAME,
                    password=PASSWORD
                )
            )
        )
        self.channel = self.connection.channel()                      
        queue = self.channel.queue_declare(queue='',exclusive=True,auto_delete=True)
        event_listener = queue.method.queue
        self.channel.queue_bind(exchange='X:routing.topic',queue=event_listener,routing_key='event.state.'+room_id)
        self.channel.basic_consume(
            queue=event_listener,
            on_message_callback=self.on_response,
            auto_ack=True
        )
        self.response = None

    def on_response(self, ch, method, props, body):
        self.response = json.loads(body)
        
        

    def run(self):
        self.channel.start_consuming()

UP = 'UP'
DOWN = 'DOWN'
LEFT = 'LEFT'
RIGHT = 'RIGHT'


MOVE_KEYS = {
    pygame.K_UP: UP,
    pygame.K_LEFT: LEFT,
    pygame.K_DOWN: DOWN,
    pygame.K_RIGHT: RIGHT
}

def draw_tank(x, y, width, height, color, direction, name):
    tank_c = (x + int(width / 2), y + int(width / 2))
    pygame.draw.rect(screen, color, (x, y, width, width), 2)
    pygame.draw.circle(screen, color, tank_c, int(width / 2))
    if direction == RIGHT:
        pygame.draw.line(screen, color, tank_c, (x + width + width // 2, y + height // 2), 2)
    if direction == LEFT:
        pygame.draw.line(screen, color, tank_c, (x - width + width // 2, y + width // 2), 2)
    if direction == UP:
        pygame.draw.line(screen, color, tank_c, (x + width // 2, y - width // 2), 2)
    if direction == DOWN:
        pygame.draw.line(screen, color, tank_c, (x + width // 2, y + height + width // 2), 2)
    font = pygame.font.Font('freesansbold.ttf', 20) 
    text = font.render(name, True, (0, 0, 0))
    textRect = text.get_rect() 
    textRect.center = (x, y)
    screen.blit(text, textRect)






multiplayer = False

def multi():
    screen = pygame.display.set_mode((1000, 600))
    client = TankRpcClient()
    client.check_server_status()
    client.obtain_token('room-2')
    event_client = TankConsumerClient('room-2')
    event_client.start()
    global multiplayer
    multiplayer = True
    font1 = pygame.font.SysFont("comicsansms", 20)
    while multiplayer:
        screen.fill((255, 255, 255))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                multiplayer = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    multiplayer = False
                if event.key in MOVE_KEYS:
                    client.turn_tank(client.token, MOVE_KEYS[event.key])
                if event.key == pygame.K_SPACE:
                    client.fire_bullet(client.token)

        try:
            remaining_time = event_client.response['remainingTime']
            text = font1.render('Remaining Time: {}'.format(remaining_time), True, (255, 0, 0))
            textRect = text.get_rect()
            textRect.center = (350, 30)
            screen.blit(text, textRect)
            hits = event_client.response['hits']
            bullets = event_client.response['gameField']['bullets']
            winners = event_client.response['winners']
            tanks = event_client.response['gameField']['tanks']
            pygame.draw.rect(screen, (0, 0, 0), (820, 0, 180, 600), 7)
            i = 30
            for tank in tanks:
                tank_x = tank['x']
                tank_y = tank['y']
                tank_width = tank['width']
                tank_height = tank['height']
                tank_direction = tank['direction']
                tank_Id = tank['id']
                scores = {tank['id']: [tank['score'],tank['health']]}
                sorted_scores = reversed(sorted(scores.items(), key=lambda kv: kv[1]))
                font3 = pygame.font.Font('freesansbold.ttf', 20)
                for score in sorted_scores:
                    table = font3.render(str(score[0])+":   "+str(score[1][1])+'    '+str(score[1][0]), True, (0, 0, 0))
                    tableRect = (830, i)
                    screen.blit(table, tableRect)
                    i+=40
                if tank_Id == client.tank_id:
                    points = tank['score']
                    draw_tank(tank_x, tank_y, tank_width, tank_height, (14, 221, 147), tank_direction, 'You')
                else:
                    draw_tank(tank_x, tank_y, tank_width, tank_height, (220, 150, 28), tank_direction, tank_Id)
                for bullet in bullets:
                    bullet_x = bullet['x']
                    bullet_y = bullet['y']
                    if bullet['owner'] == client.tank_id:
                        pygame.draw.circle(screen, (14, 221, 147), (bullet_x, bullet_y), 4)
                    else:
                        pygame.draw.circle(screen, (220, 150, 28), (bullet_x, bullet_y), 4)
            for tank in event_client.response['kicked']:
                multiplayer = False
                screen = pygame.display.set_mode((800, 600))
                if tank_Id == client.tank_id:
                    screen.fill(((255, 255, 255)))
                    kicked = font1.render("You are kicked!", True, (0, 0, 0))
                    screen.blit(kicked, (150, 250)) 
                    score = font1.render("score:" + str(points), True, (0, 0, 0))
                    screen.blit(score, (250, 350))
                    pygame.display.flip()
                    time.sleep(5)
                   

                    
            for tank in event_client.response['winners']:
                multiplayer = False
                screen = pygame.display.set_mode((800, 600))
                if tank_Id == client.tank_id:
                    screen.fill((255, 255, 255))
                    winner = font1.render("You win!", True, (0, 0,0))
                    screen.blit(winner, (150, 250))
                    score = font1.render("score:" + str(points), True, (0, 0,0))
                    screen.blit(score, (250, 350))
                    pygame.display.flip()
                    time.sleep(5)
                  

            for tank in event_client.response['losers']:
                multiplayer = False
                screen = pygame.display.set_mode((800, 600))
                if tank_Id == client.tank_id:
                    screen.fill((255, 255, 255))
                    loser = font1.render("You lose!", True, (0, 0, 0))
                    screen.blit(loser, (150, 250))
                    score = font1.render("score:" + str(points), True, (0, 0, 0))
                    screen.blit(score, (250, 350))
                    pygame.display.flip()
                    time.sleep(5)
                   
            
               

        except Exception as e:
            
            pass
        pygame.display.flip()
    
    client.connection.close()
    pygame.quit()

def multiaimode():
    client = TankRpcClient()
    client.check_server_status()
    client.obtain_token('room-2')
    event_client = TankConsumerClient('room-2')
    event_client.start()
    global aimode, my_x, my_y, tank_x, tank_y, my_direction, tank_direction
    screen = pygame.display.set_mode((1000, 600))
    font1 = pygame.font.Font('freesansbold.ttf', 20)
    client.turn_tank(client.token, LEFT) 
    while aimode:
        screen.fill((255, 255, 255))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                aimode = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    aimode = False
                # if event.key in MOVE_KEYS:
                #     client.turn_tank(client.token, MOVE_KEYS[event.key])
                # if event.key == pygame.K_SPACE:
                #     client.fire_bullet(client.token)

        try:
            remaining_time = event_client.response['remainingTime']
            text = font1.render('Remaining Time: {}'.format(remaining_time), True, (255, 0, 0))
            textRect = text.get_rect()
            textRect.center = (350, 30)
            screen.blit(text, textRect)
            hits = event_client.response['hits']
            bullets = event_client.response['gameField']['bullets']
            winners = event_client.response['winners']
            tanks = event_client.response['gameField']['tanks']
            pygame.draw.rect(screen, (0, 0, 0), (820, 0, 180, 600), 7)
            i = 30
            for tank in tanks:
                tank_x = tank['x']
                tank_y = tank['y']
                tank_width = tank['width']
                tank_height = tank['height']
                tank_direction = tank['direction']
                tank_Id = tank['id']
                scores = {tank['id']: [tank['score'],tank['health']]}
                sorted_scores = reversed(sorted(scores.items(), key=lambda kv: kv[1]))
                font3 = pygame.font.Font('freesansbold.ttf', 20)
                for score in sorted_scores:
                    table = font3.render(str(score[0])+":   "+str(score[1][1])+'    '+str(score[1][0]), True, (0, 0, 0))
                    tableRect = (830, i)
                    screen.blit(table, tableRect)
                    i+=40
                if tank_Id == client.tank_id:
                    my_x = tank['x']
                    my_y = tank['y']
                    points = tank['score']
                    my_direction = tank['direction']
                    draw_tank(tank_x, tank_y, tank_width, tank_height, (14, 221, 147), tank_direction, 'You')
                else:
                    tank_direction = tank['direction']
                    tank_x = tank['x']
                    tank_y = tank['y']
                    draw_tank(tank_x, tank_y, tank_width, tank_height, (220, 150, 28), tank_direction, tank_Id)
                    
                    if tank_x in range(my_x - 100, my_x + 100) and tank_y in range(my_y - 100, my_y + 100):
                        if tank.direction == 'UP':
                            client.turn_tank(client.token, RIGHT)

                        elif tank.direction == 'LEFT':
                            client.turn_tank(client.token, UP)

                        elif tank.direction == 'RIGHT':
                            client.turn_tank(client.token, UP)
                        
                        elif tank.direction == 'DOWN':
                            client.turn_tank(client.token, RIGHT)
                    
                    if  tank_x in range(my_x - 70, my_x + 70):

                        if my_direction == 'UP' and tank_direction == 'DOWN':
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, RIGHT) 

                        elif my_direction == 'UP' and (tank_direction == 'DOWN' or tank_direction == 'UP'):
                            client.turn_tank(client.token, DOWN) 
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, LEFT) 

                        elif (my_direction == 'UP' and tank_direction == 'UP'):
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, LEFT)


                        elif (my_direction == 'DOWN' and tank_direction == 'UP') or (my_direction == 'DOWN' and tank_direction == 'DOWN' ):
                            client.turn_tank(client.token, UP)
                            client.fire_bullet(client.token) 
                            client.turn_tank(client.token, LEFT) 

                        elif my_direction == 'DOWN' and tank_direction == 'UP':
                            client.fire_bullet(client.token) 
                            client.turn_tank(client.token, LEFT) 

                        elif my_direction == 'DOWN' and tank_direction == 'DOWN':
                            client.turn_tank(client.token,  UP)
                            client.fire_bullet(client.token) 
                            client.turn_tank(client.token, RIGHT) 


                        elif my_direction == 'DOWN' and tank_direction == 'RIGHT':
                            client.fire_bullet(client.token) 
                            client.turn_tank(client.token, LEFT)
                        
                        elif my_direction == 'DOWN' and tank_direction == 'RIGHT':
                            client.turn_tank(client.token,  UP)
                            client.fire_bullet(client.token) 
                            client.turn_tank(client.token, LEFT)
                        
                        elif my_direction == 'DOWN' and tank_direction == 'LEFT':
                            client.fire_bullet(client.token) 
                            client.turn_tank(client.token, RIGHT)
                        
                        elif my_direction == 'DOWN' and tank_direction == 'LEFT':
                            client.turn_tank(client.token,  UP)
                            client.fire_bullet(client.token) 
                            client.turn_tank(client.token, RIGHT)
                        
                        elif my_direction == 'UP' and tank_direction == 'RIGHT':
                            client.fire_bullet(client.token) 
                            client.turn_tank(client.token, LEFT)
                        
                        elif my_direction == 'UP' and tank_direction == 'RIGHT':
                            client.turn_tank(client.token,  DOWN)
                            client.fire_bullet(client.token) 
                            client.turn_tank(client.token, LEFT)
                        
                        elif my_direction == 'UP' and tank_direction == 'LEFT':
                            client.fire_bullet(client.token) 
                            client.turn_tank(client.token, RIGHT)
                        
                        elif my_direction == 'UP' and tank_direction == 'LEFT':
                            client.turn_tank(client.token,  DOWN)
                            client.fire_bullet(client.token) 
                            client.turn_tank(client.token, RIGHT)
                        
                    if tank_y in range(my_y - 70, my_y + 70):
                        if my_direction == 'RIGHT' and tank_direction == 'LEFT' :
                            client.turn_tank(client.token, LEFT)
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, UP) 

                        elif my_direction == 'RIGHT' and tank_direction == 'LEFT':
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, DOWN) 

                        elif my_direction == 'RIGHT' and tank_direction == 'RIGHT':
                            client.turn_tank(client.token, LEFT)
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, DOWN) 

                        elif my_direction == 'RIGHT' and tank_direction == 'RIGHT':
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, DOWN) 

                        elif my_direction == 'LEFT' and tank_direction == 'LEFT':
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, UP)

                        elif my_direction == 'LEFT' and tank_direction == 'LEFT':
                            client.turn_tank(client.token, RIGHT)
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, UP)

                        elif my_direction == 'LEFT' and tank_direction == 'RIGHT':
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, DOWN) 

                        elif my_direction == 'LEFT' and tank_direction == 'RIGHT':
                            client.turn_tank(client.token, RIGHT)
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, DOWN) 

                        elif my_direction == 'RIGHT' and tank_direction == 'DOWN':
                            client.turn_tank(client.token, LEFT) 
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, UP)

                        elif my_direction == 'RIGHT' and tank_direction == 'DOWN':
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, UP) 

                        elif my_direction == 'RIGHT' and tank_direction == 'UP':
                            client.turn_tank(client.token, LEFT) 
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, DOWN)

                        elif my_direction == 'RIGHT' and tank_direction == 'UP':
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, DOWN)

                        elif my_direction == 'LEFT' and tank_direction == 'UP':
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, DOWN)

                        elif my_direction == 'LEFT' and tank_direction == 'UP':
                            client.turn_tank(client.token, RIGHT)
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, DOWN)

                        elif my_direction == 'LEFT' and tank_direction == 'DOWN' :
                            client.turn_tank(client.token, RIGHT)
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, UP)

                        elif my_direction == 'LEFT' and tank_direction == 'DOWN'  :
                            client.fire_bullet(client.token)
                            client.turn_tank(client.token, UP)
                        
                for bullet in bullets:
                    bullet_x = bullet['x']
                    bullet_y = bullet['y']
                    if bullet['owner'] == client.tank_id:
                        pygame.draw.circle(screen, (14, 221, 147), (bullet_x, bullet_y), 4)
                    else:
                        pygame.draw.circle(screen, (220, 150, 28), (bullet_x, bullet_y), 4)

                        if bullet_x in range(my_x - 300, my_x + 300):
                            if tank_direction == 'LEFT':
                                client.turn_tank(client.token, UP)
                            if tank_direction == 'RIGHT':
                                client.turn_tank(client.token, UP)
                            if tank_direction == 'UP':
                                client.turn_tank(client.token, RIGHT)
                            if tank_direction == 'DOWN':
                                client.turn_tank(client.token, RIGHT)
            for tank in event_client.response['kicked']:
                aimode = False
                screen = pygame.display.set_mode((800, 600))
                if tank_Id == client.tank_id:
                    screen.fill(((255, 255, 255)))
                    kicked = font1.render("You are kicked!", True, (0, 0, 0))
                    screen.blit(kicked, (150, 250)) 
                    score = font1.render("score:" + str(points), True, (0, 0, 0))
                    screen.blit(score, (250, 350))
                    pygame.display.flip()
                    time.sleep(5)
                   

                    
            for tank in event_client.response['winners']:
                aimode = False
                screen = pygame.display.set_mode((800, 600))
                if tank_Id == client.tank_id:
                    screen.fill((255, 255, 255))
                    winner = font1.render("You win!", True, (0, 0,0))
                    screen.blit(winner, (150, 250))
                    score = font1.render("score:" + str(points), True, (0, 0,0))
                    screen.blit(score, (250, 350))
                    pygame.display.flip()
                    time.sleep(5)
                  

            for tank in event_client.response['losers']:
                aimode = False
                screen = pygame.display.set_mode((800, 600))
                if tank_Id == client.tank_id:
                    screen.fill((255, 255, 255))
                    loser = font1.render("You lose!", True, (0, 0, 0))
                    screen.blit(loser, (150, 250))
                    score = font1.render("score:" + str(points), True, (0, 0, 0))
                    screen.blit(score, (250, 350))
                    pygame.display.flip()
                    time.sleep(5)
                   
            
               

        except Exception as e:
            
            pass
        pygame.display.flip()
    
    client.connection.close()
    pygame.quit()

# client = TankRpcClient()
# client.check_server_status()
# client.obtain_token('room-2')
# event_client = TankConsumerClient('room-2')
# event_client.start()

def mainmenushka():
    global mainmenu, multiplayer, aimode, screen
    while mainmenu:
        screen.fill((251, 193, 178))
        for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    mainmenu = False
                    pygame.quit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1:
                        mainmenu = False
                        #single loop = True
                    if event.key == pygame.K_2:
                        mainmenu = False
                        multiplayer = True
                        multi()
                    if event.key == pygame.K_3:
                        mainmenu = False
                        aimode = True
                        multiaimode()
        
        pygame.draw.rect(screen, (0, 193, 178),(30,400,200,70))
        pygame.draw.rect(screen, (0, 193, 178),(300,400,200,70))
        pygame.draw.rect(screen, (0, 193, 178),(570,400,200,70))

        text1 = font1.render('Tap 1 for single', True, (0,0,0))
        screen.blit(text1, (35,410))
        text2 = font1.render('Tap 2 for multiplayer', True, (0,0,0))
        screen.blit(text2, (302,410))
        text3 = font1.render('Tap 3 for AI mode', True, (0,0,0))
        screen.blit(text3, (575,410))
        screen.blit(welcome, (280,100))
        pygame.display.flip()
mainmenushka()
    
pygame.init()
screen = pygame.display.set_mode((800, 600))

pygame.display.set_caption('Tank Game')
background = pygame.image.load('background.jpg') 
GameOver_1 = pygame.image.load('Gameover1.png')
GameOver_2 = pygame.image.load('Gameover2.png')
tankshoot = pygame.mixer.Sound('shot.wav')
gameoversound = pygame.mixer.Sound('gameover.wav')

font = pygame.font.SysFont('arial', 30)

change1 = True
change2 = True
isGameOver1 = False
isGameOver2 = False

class Bullets:

    def __init__(self, x, y, speedx, speedy):
        self.x = x
        self.y = y
        self.speedx = speedx
        self.speedy = speedy
        self.shot = False
        self.speedx0 = speedx
        self.speedy0 = speedy

    def draw(self):
        pygame.draw.circle(screen, (255, 0, 0), (self.x, self.y),8)

    def move(self):

        if self.shot == True:
            self.x += self.speedx
            self.y += self.speedy

        self.draw()
        
class Direction(Enum):
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4

class Tank:

    def __init__(self, x, y, speed, color, d_right=pygame.K_RIGHT, d_left=pygame.K_LEFT, d_up=pygame.K_UP, d_down=pygame.K_DOWN):
        self.x = x
        self.y = y
        self.speed = speed
        self.speed0 = speed
        self.color = color
        self.width = 40
        self.direction = Direction.RIGHT

        self.KEY = {d_right: Direction.RIGHT, d_left: Direction.LEFT,
                    d_up: Direction.UP, d_down: Direction.DOWN}

    def draw(self):
        tank_c = (self.x + int(self.width / 2), self.y + int(self.width / 2))
        pygame.draw.rect(screen, self.color,
                         (self.x, self.y, self.width, self.width), 2)
        pygame.draw.circle(screen, self.color, tank_c, int(self.width / 2))

        if self.direction == Direction.RIGHT:
            pygame.draw.line(screen, self.color, tank_c, (self.x + self.width + int(self.width / 2), self.y + int(self.width / 2)), 4)

        if self.direction == Direction.LEFT:
            pygame.draw.line(screen, self.color, tank_c, (
            self.x - int(self.width / 2), self.y + int(self.width / 2)), 4)

        if self.direction == Direction.UP:
            pygame.draw.line(screen, self.color, tank_c, (self.x + int(self.width / 2), self.y - int(self.width / 2)), 4)

        if self.direction == Direction.DOWN:
            pygame.draw.line(screen, self.color, tank_c, (self.x + int(self.width / 2), self.y + self.width + int(self.width / 2)), 4)

    def change_direction(self, direction):
        self.direction = direction

    def move(self):
        if self.direction == Direction.LEFT:
            self.x -= self.speed
        if self.direction == Direction.RIGHT:
            self.x += self.speed
        if self.direction == Direction.UP:
            self.y -= self.speed
        if self.direction == Direction.DOWN:
            self.y += self.speed
      
        if (self.x+self.width < 0):
            self.x = 800
        if (self.x > 800):
            self.x = 0-self.width
        if (self.y+self.width < 0):
            self.y = 600
        if (self.y > 600):
            self.y = 0-self.width
        
        self.draw()

class Wall:
    def __init__(self):
        self.x = random.randint(150,450)
        self.y = random.randint(150,450)
        self.color = (14,47,178)
        self.height = 60
        self.width = 60
        self.status = True
    def draw(self):
        pygame.draw.rect(screen,self.color,(self.x,self.y,self.height,self.width))

class Food:
    def __init__(self):
        self.x = random.randint(450,600)
        self.y = random.randint(450,600)
        self.status = True
    
    def draw(self):
        if self.status:
            font = pygame.font.Font('freesansbold.ttf', 32) 
            text = font.render('S', True, (0, 255, 0), (34, 77, 23)) 
            screen.blit(text,(self.x,self.y)) 
    def superpower(self):
        if sec2 <= 5:
            for tank in tanks:
                tank.speed = (int(tank.speed0) * 2)
            for bullet in bullets:
                bullet.speedx = (int(bullet.speedx0) * 2)
                bullet.speedy = (int(bullet.speedy0) * 2)
        else:
            for tank in tanks:
                tank.speed = int(tank.speed0 )
            for bullet in bullets:
                bullet.speedx = int(bullet.speedx0 )
                bullet.speedy = int(bullet.speedy0 )



def give_coordinates(tank):
    if tank.direction == Direction.RIGHT:
        x=tank.x + tank.width + int(tank.width / 2) #ЧТОБ РОВНО С СЕРЕДИНЫ ТАНКА ПУЛЯ ВЫЛЕТИЛА
        y=tank.y + int(tank.width / 2)

    if tank.direction == Direction.LEFT:
        x=tank.x - int(tank.width / 2)
        y=tank.y + int(tank.width / 2)

    if tank.direction == Direction.UP:
        x=tank.x + int(tank.width / 2)
        y=tank.y - int(tank.width / 2)

    if tank.direction == Direction.DOWN:
        x=tank.x + int(tank.width / 2)
        y=tank.y + tank.width + int(tank.width / 2)

    bullet=Bullets(x,y,tank.color,tank.direction) 
    bullets.append(bullet) 

score1 = 3
score2 = 3


tank1 = Tank(100, 100, 1, (100, 0, 0))
tank2 = Tank(300, 300, 1, (0, 100, 0), pygame.K_d, pygame.K_a, pygame.K_w, pygame.K_s)

tanks = [tank1, tank2]
bullet1 = Bullets(831, 560, 0, 0)
bullet2 = Bullets(831, 560, 0, 0)
bullets = [bullet1,bullet2]
food = Food()
wall1 = Wall()
wall2 = Wall()
wall3 = Wall()
wall4 = Wall()
wall5 = Wall()
wall6 = Wall()

vse_walls = [wall1, wall2,wall3,wall4,wall5,wall6]

pygame.time.set_timer(pygame.USEREVENT, 1000)
clock = pygame.time.Clock ()
keys = pygame.key.get_pressed()

sec1 = 0
sec2 = 0
bonus = False
bonustime = random.randint(5,10)
foodimage = pygame.image.load("food.png")

mainloop = True
while mainloop:
    clock.tick(100)
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            mainloop = False
        if event.type == pygame.USEREVENT: 
            sec1 += 1
            if bonus:
                sec2 += 1
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                mainloop = False
            
            for tank in tanks:
                if event.key in tank.KEY.keys():
                    tank.change_direction(tank.KEY[event.key])

            if event.key == pygame.K_RETURN and bullet1.shot == False:
                tankshoot.play()
                
                bullet1.shot = True
                if tank1.direction == Direction.LEFT:
                    bullet1.x = tank1.x - 20
                    bullet1.y = tank1.y + 20
                    bullet1.speedx = -10
                    bullet1.speedy = 0
                if tank1.direction == Direction.RIGHT:
                    bullet1.x = tank1.x + 60
                    bullet1.y = tank1.y + 20
                    bullet1.speedx = 10
                    bullet1.speedy = 0
                if tank1.direction == Direction.UP:
                    bullet1.x = tank1.x + 20
                    bullet1.y = tank1.y - 20
                    bullet1.speedx = 0
                    bullet1.speedy = -10
                if tank1.direction == Direction.DOWN:
                    bullet1.x = tank1.x + 20
                    bullet1.y = tank1.y + 60
                    bullet1.speedx = 0
                    bullet1.speedy = 10

            if event.key == pygame.K_SPACE and bullet2.shot == False:
                tankshoot.play()
                give_coordinates(tank)
            
                bullet2.shot = True
                bullet2.x = tank2.x
                bullet2.y = tank2.y
                if tank2.direction == Direction.LEFT:
                    bullet2.x = tank2.x - 20
                    bullet2.y = tank2.y + 20
                    bullet2.speedx = -10
                    bullet2.speedy = 0
                if tank2.direction == Direction.RIGHT:
                    bullet2.x = tank2.x + 60
                    bullet2.y = tank2.y + 20
                    bullet2.speedx = 10
                    bullet2.speedy = 0
                if tank2.direction == Direction.UP:
                    bullet2.x = tank2.x + 20
                    bullet2.y = tank2.y - 20
                    bullet2.speedx = 0
                    bullet2.speedy = -10
                if tank2.direction == Direction.DOWN:
                    bullet2.x = tank2.x + 20
                    bullet2.y = tank2.y + 60
                    bullet2.speedx = 0
                    bullet2.speedy = 10

    if bullet1.x < 0 or bullet1.x > 821 or bullet1.y < 0 or bullet1.y > 550:
        bullet1.shot = False
    if bullet2.x < 0 or bullet2.x > 821 or bullet2.y < 0 or bullet2.y > 550:
        bullet2.shot = False

    if bullet1.x in range(tank2.x, tank2.x + 40) and bullet1.y in range(tank2.y, tank2.y + 40):
        
        bullet1.shot = False
        bullet1.x = 810
        bullet1.y = 610
        score1 -= 1
        change1 = True
    
    if bullet2.x in range(tank1.x, tank1.x + 40) and bullet2.y in range(tank1.y, tank1.y + 40):
        
        bullet2.shot = False
        bullet2.x = 810
        bullet2.y = 610
        score2 -=1 
        change2 = True

    if change1 == True:
        score_1 = font.render("Health of 1 tank: " + str(score1), True, (255,255,255))
        change1 = False
    
    if change2 == True:
        score_2 = font.render("Health of 2 tank: " + str(score2), True, (255,255,255))
        change2 = False
    for bullet in bullets:
        for wall in vse_walls:
            if (wall.x+wall.width+5 > bullet.x> wall.x-5) and (wall.y + wall.width + 5 > bullet.y > wall.y - 5): #and bullet.status == True:
                tankshoot.play()
                bullet.color = (0,0,0)
                bullet.status = False 

                
                wall.x=random.randint(100,600-100)
                wall.y=random.randint(100,600-30)

    for wall in  vse_walls:
        for tank in tanks:
            lx1 = wall.x
            lx2 = tank.x

            rx1 = wall.x + wall.width 
            rx2 = tank.x + tank.width 

            ty1 = wall.y 
            ty2 = tank.y 

            by1 = wall.y + wall.height
            by2 = tank.y + tank.width 

            lx = max(lx1, lx2)
            rx = min(rx1, rx2)
            ty = max(ty1, ty2)
            by = min(by1, by2)

            if lx<=rx and ty<=by:
                tankshoot.play()
                #tank.score -= 1
                tank.x=random.randint(40,500-70)
                tank.y=random.randint(40,500-70)
                #score1 -= 1
            
    screen.fill((128, 128, 128))
    screen.blit(background, (0,0))
    screen.blit(score_1, (100, 10))
    screen.blit(score_2, (600, 10))
    tank1.move()
    tank2.move()
    bullet1.move()
    bullet2.move()
    foods = [food]

    for wall in vse_walls:
            wall.draw()
    
    if score1 <= 0 :
        isGameOver1 = True
        gameoversound.play()
    
        if isGameOver1 == True:
            screen.blit(GameOver_1 , (0, 0))
        elif keys[pygame.K_SPACE] or keys[pygame.K_RETURN]:
            screen.blit(GameOver_1 , (0, 0))
             
    if score2 <= 0 :
        isGameOver2 = True
        gameoversound.play()

        if isGameOver2 == True :
            screen.blit(GameOver_2 , (0, 0))
        elif keys[pygame.K_SPACE] or keys[pygame.K_RETURN]:
            screen.blit(GameOver_2 , (0, 0))
    
    if sec1 >= bonustime:
        if bonus == False: screen.blit(foodimage,(food.x, food.y))
        for tank in tanks:
            if food.x <= tank.x + 20 <= food.x + 40:
                if food.y <= tank.y + 20 <=food.y + 40:
                    bonus = True
                    food.superpower()

    pygame.display.flip()

pygame.quit() 