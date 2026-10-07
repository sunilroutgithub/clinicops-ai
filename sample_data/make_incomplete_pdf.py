import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

out = os.path.join(os.path.dirname(__file__), "incomplete_insurance.pdf")
c = canvas.Canvas(out, pagesize=A4)

lines = [
    "SAMPLE HEALTH INSURANCE CARD (FAKE DATA)",
    "",
    "Patient: Jane Doe",
    "Insurance Provider: Sample Health Insurance Co.",
]
y = 780
for line in lines:
    c.drawString(72, y, line)
    y -= 24
c.save()
print("Created", out)