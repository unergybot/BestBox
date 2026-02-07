from PIL import Image, ImageDraw

def create_image():
    img = Image.new('RGB', (100, 30), color = (73, 109, 137))
    d = ImageDraw.Draw(img)
    d.text((10,10), "Hello World", fill=(255, 255, 0))
    img.save('test.png')
    print("Created test.png")

if __name__ == "__main__":
    create_image()
