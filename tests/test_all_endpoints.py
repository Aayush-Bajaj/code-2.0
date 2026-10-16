import urllib.request
import json
import io
import os
import sys

base_url = 'http://127.0.0.1:8000'

def post_json(path, data):
    url = f'{base_url}{path}'
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))

def get_url(path):
    url = f'{base_url}{path}'
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return resp.status, resp.read()

def run_tests():
    print("=== 1. Health & Meta Endpoints ===")
    status, body = get_url('/api/health')
    assert status == 200
    print("[PASS] /api/health")

    status, body = get_url('/meta/sources')
    assert status == 200
    print("[PASS] /meta/sources")

    status, body = get_url('/meta/equivalents?co2e_kg=22557.1')
    assert status == 200
    print("[PASS] /meta/equivalents")

    status, body = get_url('/api/vision/smoke/status')
    assert status == 200
    print("[PASS] /api/vision/smoke/status")

    print("\n=== 2. Calculate Endpoint ===")
    calc_payload = {
        'bills': [
            {
                'id': 'b1', 'source_file': 'bill.pdf', 'bill_type': 'electricity',
                'period_start': '2024-03-01', 'period_end': '2024-03-31',
                'quantity': 18450.0, 'unit': 'kWh', 'amount_inr': 162360.0,
                'supplier': 'MSEDCL', 'confidence_0_1': 0.95, 'field_boxes': {}, 'method': 'ocr'
            },
            {
                'id': 'b2', 'source_file': 'diesel.pdf', 'bill_type': 'diesel',
                'period_start': '2024-03-01', 'period_end': '2024-03-31',
                'quantity': 1250.0, 'unit': 'L', 'amount_inr': 115625.0,
                'supplier': 'IOCL', 'confidence_0_1': 0.95, 'field_boxes': {}, 'method': 'ocr'
            },
            {
                'id': 'b3', 'source_file': 'freight.pdf', 'bill_type': 'freight',
                'period_start': '2024-03-01', 'period_end': '2024-03-31',
                'quantity': 30400.0, 'unit': 'tonne-km', 'amount_inr': 182400.0,
                'supplier': 'VRL Logistics', 'confidence_0_1': 0.95, 'field_boxes': {}, 'method': 'ocr'
            }
        ],
        'gensets': [
            {
                'detection': {
                    'id': 'det_dg_01', 'source_file': 'genset.mp4', 'frame_index': 10,
                    'frame_path': 'data/evidence/frames/genset.jpg', 'machine_type': 'diesel_generator',
                    'fuel_type': 'diesel', 'rated_power_kw': 100.0, 'rated_kva': 125.0,
                    'nameplate_text': 'KIRLOSKAR GREEN 100 kW',
                    'smoke': {'level': 'heavy', 'color': 'black', 'score_0_10': 8.2},
                    'maintenance_flag': True, 'confidence_0_1': 0.92
                },
                'hours_per_month': 45.0,
                'load_pct': 75.0
            }
        ]
    }
    status, calc_res = post_json('/api/calculate', calc_payload)
    assert status == 200
    grand_total = calc_res['totals']['grand_total']['co2e_kg']
    print(f"[PASS] /api/calculate -> lines: {len(calc_res['emission_lines'])}, total CO2e: {grand_total}")

    print("\n=== 3. Scenario Simulate Endpoint ===")
    sim_payload = {
        'baseline_lines': calc_res['emission_lines'],
        'inputs': {
            'solar_share_pct': 30,
            'genset_hours_reduction_pct': 20,
            'idle_hours_reduction_pct': 10,
            'electric_forklift': 1,
            'rail_shift_pct': 15
        }
    }
    status, sim_res = post_json('/api/scenarios/simulate', sim_payload)
    assert status == 200
    assert len(sim_res['ranked_levers']) == 5
    print(f"[PASS] /api/scenarios/simulate -> delta: {sim_res['delta_pct']}%, new CO2e: {sim_res['new_co2e_kg']}, ranked: {len(sim_res['ranked_levers'])}")

    print("\n=== 4. Report Generation Endpoint ===")
    rep_payload = {
        'facility_name': 'Sharma Auto Components Pvt. Ltd.',
        'reporting_period': '2024-Q1',
        'emission_lines': calc_res['emission_lines'],
        'scenario_result': sim_res
    }
    status, rep_res = post_json('/report', rep_payload)
    assert status == 200
    report_id = rep_res['facts_snapshot']['report_id']
    print(f"[PASS] /report -> report_id: {report_id}")

    print("\n=== 5. PDF Generation & Download Endpoint ===")
    status, pdf_bytes = get_url(f'/report/{report_id}/pdf')
    assert status == 200
    assert pdf_bytes.startswith(b'%PDF'), "PDF magic bytes missing"
    print(f"[PASS] /report/{report_id}/pdf -> {len(pdf_bytes)} bytes received")

    print("\n=== ALL BACKEND ENDPOINTS PASSED CLEANLY ===")

if __name__ == '__main__':
    run_tests()
