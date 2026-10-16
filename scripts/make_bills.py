#!/usr/bin/env python3
"""
Generate 15 synthetic Indian utility and freight bills (PNG) using Pillow.
- 5 Electricity bills (kWh)
- 5 Diesel fuel bills (Litres)
- 5 Freight logistics bills (tonne-km / kg)
Features:
- Fictional Indian suppliers
- Varied layouts and fonts
- Indian numbering format: e.g. 1,23,456.00
- dd/mm/yyyy dates
- Half of bills with realistic scan artifacts (rotation, blur, noise, shadow)
- Small footer: 'SYNTHETIC SAMPLE'
- Ground truth JSON written to data/bills/ground_truth.json
"""
import os
import json
import random
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR = Path(__file__).resolve().parent.parent
BILLS_DIR = BASE_DIR / "data" / "bills"
BILLS_DIR.mkdir(parents=True, exist_ok=True)


def format_inr(number: float) -> str:
    """Format number into Indian numbering system: 1,23,456.00"""
    parts = f"{number:.2f}".split(".")
    integer_part = parts[0]
    decimal_part = parts[1]

    if len(integer_part) <= 3:
        formatted_int = integer_part
    else:
        last3 = integer_part[-3:]
        rest = integer_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted_int = ",".join(groups) + "," + last3

    return f"Rs. {formatted_int}.{decimal_part}"


def format_indian_number(num: float, decimals: int = 1) -> str:
    """Format quantity into Indian number formatting."""
    fmt = f"{num:.{decimals}f}"
    parts = fmt.split(".")
    integer_part = parts[0]
    decimal_part = parts[1] if len(parts) > 1 else ""

    if len(integer_part) <= 3:
        formatted_int = integer_part
    else:
        last3 = integer_part[-3:]
        rest = integer_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted_int = ",".join(groups) + "," + last3

    return f"{formatted_int}.{decimal_part}" if decimal_part else formatted_int


def add_scan_artifacts(img: Image.Image) -> Image.Image:
    """Apply random slight rotation, noise, blur, and lighting gradients."""
    # 1. Subtle lighting shadow (gradient)
    w, h = img.size
    shadow = Image.new("L", (w, h), 255)
    sdraw = ImageDraw.Draw(shadow)
    top_darkness = random.randint(220, 245)
    bottom_darkness = random.randint(235, 255)
    for y in range(h):
        val = int(top_darkness + (bottom_darkness - top_darkness) * (y / h))
        sdraw.line([(0, y), (w, y)], fill=val)
    
    img_gray = img.convert("RGBA")
    shadow_rgba = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # Multiply shadow
    img = Image.composite(img, Image.new("RGB", (w, h), (235, 235, 230)), shadow)

    # 2. Add subtle Gaussian blur
    if random.random() > 0.4:
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.5, 0.9)))

    # 3. Add random rotation (-1.8 to +1.8 degrees)
    angle = random.uniform(-1.8, 1.8)
    img = img.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))

    return img


def generate_bills():
    random.seed(42)
    ground_truth = {}

    elec_suppliers = [
        "Maharashtra State Electricity Distribution Co. Ltd. (MSEDCL)",
        "Tata Power Distribution Mumbai Ltd.",
        "Bangalore Electricity Supply Company (BESCOM)",
        "Torrent Power Surat Ltd.",
        "Dakshin Haryana Bijli Vitran Nigam (DHBVN)",
    ]

    diesel_suppliers = [
        "Indian Oil Corporation - Bhosari Fuel Point, Pune",
        "Bharat Petroleum Highway Depot - Chakan MIDC",
        "Hindustan Petroleum Industrial Fuelling, Pune",
        "Shell Commercial Fleet Fuels - Talegaon Station",
        "Nayara Energy Commercial Fuels - PCMC Bulk",
    ]

    freight_suppliers = [
        "VRL Logistics Ltd. - Western Hub",
        "TCI Freight Logistics Express, Pune",
        "Gati Kintetsu Express Surface Cargo",
        "Safechem Intercity Transport Solutions",
        "Blue Dart Surface Heavy Transport",
    ]

    # 1. Generate 5 Electricity Bills
    for i in range(1, 6):
        file_id = f"bill_elec_{i:02d}"
        filename = f"{file_id}.png"
        filepath = BILLS_DIR / filename

        qty_kwh = round(random.uniform(4200.0, 18500.0), 1)
        rate = round(random.uniform(8.10, 11.40), 2)
        total_inr = round(qty_kwh * rate, 2)
        supplier = elec_suppliers[i - 1]
        bill_date = f"{random.randint(1, 28):02d}/{random.randint(1, 12):02d}/2024"
        period_start = f"01/{i:02d}/2024"
        period_end = f"28/{i:02d}/2024"

        # Image canvas
        w, h = 900, 1150
        img = Image.new("RGB", (w, h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Draw decorative header
        draw.rectangle([(30, 30), (870, 110)], fill=(238, 242, 250), outline=(50, 70, 120), width=2)
        draw.text((50, 45), supplier.upper(), fill=(20, 35, 80))
        draw.text((50, 75), f"ELECTRICITY INVOICE / TARIFF BILL  |  BILL NO: ELEC-MH-2024-{i*1482}", fill=(60, 60, 60))

        # Consumer info
        draw.rectangle([(30, 130), (870, 220)], outline=(180, 180, 180), width=1)
        draw.text((50, 145), "Consumer Name: SHARMA AUTO COMPONENTS PVT. LTD.", fill=(0, 0, 0))
        draw.text((50, 170), "Consumer No: 054819284102   |   HT-Industrial Tariff Category", fill=(40, 40, 40))
        draw.text((50, 195), f"Billing Period: {period_start} to {period_end}   |   Bill Date: {bill_date}", fill=(40, 40, 40))

        # Meter Reading Table
        draw.rectangle([(30, 240), (870, 520)], outline=(120, 120, 120), width=2)
        draw.line([(30, 285), (870, 285)], fill=(120, 120, 120), width=2)
        draw.text((50, 255), "DESCRIPTION / CHARGES", fill=(20, 20, 20))
        draw.text((500, 255), "UNITS (kWh)", fill=(20, 20, 20))
        draw.text((680, 255), "AMOUNT (INR)", fill=(20, 20, 20))

        draw.text((50, 310), "Active Energy Recorded Units (Billed kWh):", fill=(0, 0, 0))
        draw.text((500, 310), f"{format_indian_number(qty_kwh, 1)} kWh", fill=(0, 0, 0))
        draw.text((680, 310), format_inr(total_inr), fill=(0, 0, 0))

        draw.text((50, 350), f"Energy Charge Rate @ Rs. {rate:.2f} per unit", fill=(80, 80, 80))
        draw.text((50, 390), "Demand Charges & Wheeling Fees included", fill=(80, 80, 80))
        draw.text((50, 430), "TOD Peak Surcharge / Rebate factored in total", fill=(80, 80, 80))

        # Total Box
        draw.rectangle([(480, 540), (870, 610)], fill=(245, 245, 245), outline=(0, 0, 0), width=2)
        draw.text((500, 555), "NET PAYABLE AMOUNT:", fill=(0, 0, 0))
        draw.text((500, 580), format_inr(total_inr), fill=(180, 0, 0))

        # Footer
        draw.text((380, 1110), "SYNTHETIC SAMPLE", fill=(160, 160, 160))

        if i % 2 == 1:
            img = add_scan_artifacts(img)

        img.save(filepath)

        ground_truth[filename] = {
            "bill_id": file_id,
            "bill_type": "electricity",
            "supplier": supplier,
            "period_start": period_start,
            "period_end": period_end,
            "quantity": qty_kwh,
            "unit": "kWh",
            "rate_per_unit_inr": rate,
            "amount_inr": total_inr,
            "is_scanned_artifact": (i % 2 == 1),
        }

    # 2. Generate 5 Diesel Fuel Bills
    for i in range(1, 6):
        file_id = f"bill_diesel_{i:02d}"
        filename = f"{file_id}.png"
        filepath = BILLS_DIR / filename

        qty_litres = round(random.uniform(250.0, 1400.0), 2)
        rate = round(random.uniform(89.50, 94.80), 2)
        total_inr = round(qty_litres * rate, 2)
        supplier = diesel_suppliers[i - 1]
        bill_date = f"{random.randint(1, 28):02d}/{random.randint(1, 12):02d}/2024"

        w, h = 850, 1050
        img = Image.new("RGB", (w, h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Header
        draw.text((50, 40), supplier.upper(), fill=(140, 30, 20))
        draw.text((50, 70), "TAX INVOICE - COMMERCIAL HIGH SPEED DIESEL (HSD)", fill=(60, 60, 60))
        draw.line([(50, 100), (800, 100)], fill=(0, 0, 0), width=2)

        # Buyer info
        draw.text((50, 120), "Billed To: Sharma Auto Components, Plot 42, Bhosari MIDC, Pune", fill=(20, 20, 20))
        draw.text((50, 145), f"Invoice No: DSL-2024-B{i*319}   |   Date: {bill_date}", fill=(40, 40, 40))
        draw.text((50, 170), "Delivery Purpose: Captive DG Set / Plant Forklift Generator", fill=(40, 40, 40))

        # Fuel Table
        draw.rectangle([(50, 210), (800, 420)], outline=(100, 100, 100), width=1)
        draw.text((70, 230), "Item: High Speed Diesel (BS-VI)", fill=(0, 0, 0))
        draw.text((70, 270), f"Quantity (Litres): {format_indian_number(qty_litres, 2)} L", fill=(0, 0, 0))
        draw.text((70, 310), f"Unit Rate: Rs. {rate:.2f} / Litre", fill=(0, 0, 0))
        draw.text((70, 350), f"Total Invoice Value: {format_inr(total_inr)}", fill=(0, 0, 0))

        draw.rectangle([(450, 450), (800, 520)], fill=(240, 245, 240), outline=(0, 120, 0), width=2)
        draw.text((470, 465), "TOTAL AMOUNT PAID:", fill=(0, 80, 0))
        draw.text((470, 490), format_inr(total_inr), fill=(0, 80, 0))

        draw.text((360, 1010), "SYNTHETIC SAMPLE", fill=(170, 170, 170))

        if i % 2 == 1:
            img = add_scan_artifacts(img)

        img.save(filepath)

        ground_truth[filename] = {
            "bill_id": file_id,
            "bill_type": "diesel",
            "supplier": supplier,
            "period_start": bill_date,
            "period_end": bill_date,
            "quantity": qty_litres,
            "unit": "L",
            "rate_per_unit_inr": rate,
            "amount_inr": total_inr,
            "is_scanned_artifact": (i % 2 == 1),
        }

    # 3. Generate 5 Freight Bills
    for i in range(1, 6):
        file_id = f"bill_freight_{i:02d}"
        filename = f"{file_id}.png"
        filepath = BILLS_DIR / filename

        # 3 in tonne-km, 2 in kg
        unit = "tonne-km" if i <= 3 else "kg"
        if unit == "tonne-km":
            qty = round(random.uniform(1200.0, 9500.0), 1)
            rate = round(random.uniform(4.50, 7.20), 2)
        else:
            qty = round(random.uniform(2800.0, 14500.0), 1)
            rate = round(random.uniform(3.10, 5.80), 2)

        total_inr = round(qty * rate, 2)
        supplier = freight_suppliers[i - 1]
        bill_date = f"{random.randint(1, 28):02d}/{random.randint(1, 12):02d}/2024"

        w, h = 880, 1100
        img = Image.new("RGB", (w, h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(40, 40), (840, 120)], fill=(250, 245, 235), outline=(150, 100, 30), width=2)
        draw.text((60, 55), supplier.upper(), fill=(100, 50, 10))
        draw.text((60, 85), f"CONSIGNMENT FREIGHT NOTE  |  LR NO: FRT-MH-{i*2043}", fill=(50, 50, 50))

        draw.text((60, 140), "Consignor: Sharma Auto Components, Bhosari MIDC, Pune", fill=(0, 0, 0))
        draw.text((60, 165), "Consignee: Tier-1 OEM Assembly Plant, Sanand / Chennai Hub", fill=(0, 0, 0))
        draw.text((60, 190), f"Booking Date: {bill_date}   |   Vehicle Type: 16-Ton Multi-Axle Rigid Truck", fill=(50, 50, 50))

        draw.rectangle([(40, 230), (840, 450)], outline=(120, 120, 120), width=1)
        draw.text((60, 250), f"Freight Activity Metric: {unit}", fill=(0, 0, 0))
        draw.text((60, 290), f"Recorded Consignment Volume: {format_indian_number(qty, 1)} {unit}", fill=(0, 0, 0))
        draw.text((60, 330), f"Contracted Freight Tariff: Rs. {rate:.2f} per {unit}", fill=(0, 0, 0))
        draw.text((60, 370), f"Total Freight Charge: {format_inr(total_inr)}", fill=(0, 0, 0))

        draw.rectangle([(460, 480), (840, 550)], fill=(245, 240, 250), outline=(90, 40, 130), width=2)
        draw.text((480, 495), "TOTAL FREIGHT INVOICE:", fill=(60, 20, 90))
        draw.text((480, 520), format_inr(total_inr), fill=(60, 20, 90))

        draw.text((370, 1060), "SYNTHETIC SAMPLE", fill=(170, 170, 170))

        if i % 2 == 1:
            img = add_scan_artifacts(img)

        img.save(filepath)

        ground_truth[filename] = {
            "bill_id": file_id,
            "bill_type": "freight",
            "supplier": supplier,
            "period_start": bill_date,
            "period_end": bill_date,
            "quantity": qty,
            "unit": unit,
            "rate_per_unit_inr": rate,
            "amount_inr": total_inr,
            "is_scanned_artifact": (i % 2 == 1),
        }

    gt_file = BILLS_DIR / "ground_truth.json"
    with open(gt_file, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Generated {len(ground_truth)} bills in {BILLS_DIR}")
    print(f"Ground truth written to {gt_file}")


if __name__ == "__main__":
    generate_bills()
