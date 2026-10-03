import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

out = os.path.join(os.path.dirname(__file__), "insurance_john_smith.pdf")
c = canvas.Canvas(out, pagesize=A4)

lines = [
    "SAMPLE HEALTH INSURANCE CARD (FAKE DATA)",
    "",
    "Patient: John Smith",
    "Insurance Provider: Sample Health Insurance Co.",
    "Policy Number: SHI-123456789",
    "Referral Date: 2026-09-28",
    "Referring Doctor: Dr. Rao",
]
y = 780
for line in lines:
    c.drawString(72, y, line)
    y -= 24
c.save()
print("Created", out)