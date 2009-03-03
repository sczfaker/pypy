
from pypy.lang.gameboy import constants
from pypy.lang.gameboy.constants import SPRITE_SIZE, GAMEBOY_SCREEN_WIDTH, \
                                        GAMEBOY_SCREEN_HEIGHT

# -----------------------------------------------------------------------------

class Sprite(object):
    
    def __init__(self, video):
        self.video = video
        self.big_size = False
        self.reset()

    def reset(self):
        self.x              = 0
        self.y              = 0
        self.tile           = None
        self.object_behind_background = False
        self.x_flipped      = False
        self.y_flipped      = False
        self.tile_number    = 0
        self.palette_number = 0
        self.hidden         = True
        self.rest_attributes_and_flags = 0
        
    def get_data_at(self, address):
        return self.get_data()[address % 4]
    
    def get_data(self):
        return [self.y, self.x, self.tile_number, self.get_attributes_and_flags()]

    def set_data(self, y, x, tile_number, flags):
        """
        extracts the sprite data from an oam entry
        """
        self.extract_y_position(y)
        self.extract_x_position(x)
        self.extract_tile_number(tile_number)
        self.extract_attributes_and_flags(flags)

    def set_data_at(self, address, data):
        """
        extracts the sprite data from an oam entry
        """
        position = address % 4
        if position == 0:
            self.extract_y_position(data)
        if position == 1:
            self.extract_x_position(data)
        if position == 2:
            self.extract_tile_number(data)
        if position == 3:
            self.extract_attributes_and_flags(data)
        
    def extract_y_position(self, data):
        """
        extracts the  Y Position
        Specifies the sprites vertical position on the screen (minus 16).
        An offscreen value (for example, Y=0 or Y>=160) hides the sprite.
        """
        self.y = data # - 16
        self.hide_check()
    
    def extract_x_position(self, data):
        """
        extracts the  X Position
        Specifies the sprites horizontal position on the screen (minus 8).
        An offscreen value (X=0 or X>=168) hides the sprite, but the sprite
        still affects the priority ordering - a better way to hide a sprite is 
        to set its Y-coordinate offscreen.
        """
        self.x = data # - 8
        self.hide_check()
    
    def extract_tile_number(self, data):
        """
        extracts the Tile/Pattern Number
        Specifies the sprites Tile Number (00-FF). This (unsigned) value selects
        a tile from memory at 8000h-8FFFh. In CGB Mode this could be either in
        VRAM Bank 0 or 1, depending on Bit 3 of the following byte.
        In 8x16 mode, the lower bit of the tile number is ignored. Ie. the 
        upper 8x8 tile is "NN AND FEh", and the lower 8x8 tile is "NN OR 01h".
        """
        self.tile_number = data
    
    def extract_attributes_and_flags(self, data):
        """
        extracts the Attributes/Flags:
        Bit7   OBJ-to-BG Priority (0=OBJ Above BG, 1=OBJ Behind BG color 1-3)
                 (Used for both BG and Window. BG color 0 is always behind OBJ)
        Bit6   Y flip          (0=Normal, 1=Vertically mirrored)
        Bit5   X flip          (0=Normal, 1=Horizontally mirrored)
        Bit4   Palette number  **Non CGB Mode Only** (0=OBP0, 1=OBP1)
        """
        self.object_behind_background   = bool(data  & (1 << 7))
        self.x_flipped                  = bool(data  & (1 << 6))
        self.y_flipped                  = bool(data  & (1 << 5))
        self.palette_number             = bool(data &  (1 << 4))
        self.rest_attributes_and_flags  = data & (1+2+4+8)
        
    def get_attributes_and_flags(self):
        value = 0
        value += int(self.object_behind_background) << 7
        value += int(self.x_flipped)                << 6
        value += int(self.y_flipped)                << 5
        value += int(self.palette_number)           << 4
        value += self.rest_attributes_and_flags
        return value
        
    def hide_check(self):
        if self.y <= 0  or self.y >= GAMEBOY_SCREEN_WIDTH:
            self.hidden = True
        elif self.x <= 0  or self.x >= GAMEBOY_SCREEN_WIDTH+SPRITE_SIZE:
            self.hidden = True
        else:
            self.hidden = False
        return self.hidden
        
    def get_tile_number(self):
        #return self.tile.id
        return self.tile_number
    
    def get_width(self):
        return SPRITE_SIZE
    
    def get_height(self):
        if self.big_size:
            return 2*SPRITE_SIZE
        else:
            return SPRITE_SIZE
         
    def get_tile_size(self):
         if self.big_size:
            return 15
         else:
            return 7
        
    def intersects_current_line(self, video):
        y = self.current_line_y(video)
        return y >= 0 and y <= self.get_tile_size()
    
    def is_shown_on_current_line(self, video):
        return not self.hidden and self.intersects_current_line(video)
         
    def current_line_y(self, video):
        return video.line_y - self.y + 2 * SPRITE_SIZE
    
    def get_tile(self, video):
        if video.control.big_sprites:
             return self.get_tile_number() & 0xFE
        else:
            return self.get_tile_number()
            
    def get_tile_address(self, video):
        return (self.get_tile(video) << 4) + (self.get_draw_y(video) << 1)
        
    def get_draw_y(self, video):
        y = self.current_line_y(video)
        if self.y_flipped:
            y = self.get_tile_size() - y
        return y
                
    def draw(self, video):
        video.draw_object_tile(self)
    
    def draw_overlapped(self, video):
        video.draw_overlapped_object_tile(self)
        
# -----------------------------------------------------------------------------

class PaintSprite(Sprite):
    
    def __init__(self, line_position, sprite, video):
        Sprite.__init__(self)
        self.line_position = line_position
        self.extract_attributes(sprite, video)
        self.update_position(sprite)
        
    def extract_attributes(self, sprite, video):
        self.x              = sprite.x
        self.y              = video.line_y - sprite.y + 2 * SPRITE_SIZE
        self.tile           = sprite.tile
        self.object_behind_background = sprite.object_behind_background
        self.x_flipped      = sprite.x_flipped
        self.y_flipped      = sprite.y_flipped
        self.tile_number    = sprite.tile_number
        self.hidden         = sprite.hidden
        self.rest_attributes_and_flags = sprite.rest_attributes_and_flags
        
    def update_position(sprite):
        if sprite.y < 0 or sprite.y >= self.get_height(): return
        if sprite.y_flipped:
            self.y = self.get_height() - 1 - self.y
    
# -----------------------------------------------------------------------------


class Tile(object):
    
    def __init__(self, number, video):
        self.video = video
        self.number = number
        self.reset()
        self.data = [0x00 for i in range(2*SPRITE_SIZE)]

    def draw(self, x, y):
        pattern = self.get_pattern_at(y << 1)
        for i in range(SPRITE_SIZE):
            value = (pattern >> (SPRITE_SIZE - 1 - i)) & 0x0101
            self.video.line[x + i] = value
        
    def reset(self):
        pass
    
    def set_tile_data(self, data):
        self.data = data

    def get_data_at(self, address):
        return self.data[address % (2*SPRITE_SIZE)]
    
    def set_data_at(self, address, data):
        self.data[address % (2*SPRITE_SIZE)] = data
    
    def get_data(self):
        return self.data

    def get_pattern_at(self, address):
        return self.get_data_at(address) +\
               (self.get_data_at(address + 1) << 8)
    
# -----------------------------------------------------------------------------

class Drawable(object):
    def __init__(self, video):
        self.video = video
        self.reset()

    def get_tile_map_space(self):
        if self.upper_tile_map_selected:
            return self.video.tile_map_1
        else:
            return self.video.tile_map_0

    def reset(self):
        raise Exception("Not implemented")
 

class Window(Drawable):
    
    def reset(self):
        self.x       = 0
        self.y       = 0
        self.line_y  = 0
        self.enabled = False
        self.upper_tile_map_selected  = False
        
    def switch_on(self):
        if self.line_y == 0 and self.video.line_y > self.y:
            self.line_y = GAMEBOY_SCREEN_HEIGHT
       
    def draw_line(self, line_y):
        if line_y >= self.y and self.x < GAMEBOY_SCREEN_WIDTH+SPRITE_SIZE-1 and \
           self.line_y < GAMEBOY_SCREEN_HEIGHT:

            tile_map   = self.get_tile_map_space()
            tile_group = tile_map[self.line_y >> 5]

            self.video.draw_tiles(self.x + 1, tile_group, self.line_y)
            self.line_y += 1

# -----------------------------------------------------------------------------

class Background(Drawable):
    
    def reset(self):
        # SCROLLX and SCROLLY hold the coordinates of background to
        # be displayed in the left upper corner of the screen.
        self.scroll_x   = 0
        self.scroll_y   = 0
        self.enabled    = True
        self.upper_tile_map_selected = False
      
    def draw_clean_line(self, line_y):
        for x in range(SPRITE_SIZE+GAMEBOY_SCREEN_WIDTH+SPRITE_SIZE):
            self.video.line[x] = 0x00
    
    def draw_line(self, line_y):
        y = self.scroll_y + line_y
        x = self.scroll_x

        tile_map = self.get_tile_map_space()
        tile_group = tile_map[y >> 3]
        # print "Background"
        self.video.draw_tiles(8 - (x % 8), tile_group, y, x >> 3)
