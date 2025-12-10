# Using pytesseract example:
import cv2

img = cv2.imread("C:/Users/clcas/ttb/exclude/IMG_5272.jpg")

if img is None:
    print("Error loading image")
    
cv2.imshow("Image", img)
cv2.waitKey(0)
cv2.destroyAllWindows()