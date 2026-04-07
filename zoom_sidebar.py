from PIL import Image
img = Image.open('C:/Users/User/clawd/chrome-active.png')
sidebar = img.crop((1480, 0, 1920, 1080))
sidebar_large = sidebar.resize((880, 1080))
sidebar_large.save('C:/Users/User/clawd/sidebar-zoom.png')
print('done')
