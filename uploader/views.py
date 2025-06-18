from django.shortcuts import render
from django.http import HttpResponse
import pandas as pd
from io import BytesIO
import traceback
from datetime import datetime
from dateutil import parser
import os
import openpyxl

def home(request):
    if request.method == 'POST' and request.FILES:
        try:
            uploaded = list(request.FILES.values())
            if len(uploaded) != 2:
                return render(request, 'uploader/upload.html',
                              {'error': 'Please upload exactly two files.'})

            def read_file(f):
                file_name = f.name
                if file_name.endswith('.csv'):
                    return pd.read_csv(f, dtype=str)

                elif file_name.endswith(('.xls', '.xlsx')):
                    df = pd.read_excel(f, dtype=str)
                    base_name = os.path.splitext(file_name)[0]
                    df.to_csv(f"/tmp/{base_name}.csv", index=False)  # Optional
                    return df

                else:
                    raise ValueError("Only .csv, .xls, .xlsx files are allowed.")

            # Read uploaded files
            scheduler = read_file(uploaded[0])
            workbook = openpyxl.load_workbook(uploaded[0]) 
            sheet = workbook.active
            sc = [(sheet.iter_rows(values_only=True))]
            print(sc)
            provider = read_file(uploaded[1])

            # Clean column names
            scheduler.columns = scheduler.columns.str.strip()
            provider.columns = provider.columns.str.strip()

            # Fill blanks
            scheduler.fillna("Blank Data", inplace=True)
            provider.fillna("Blank Data", inplace=True)

            # Normalize and clean data
            scheduler['NPI'] = scheduler['NPI'].astype(str).str.strip().str.split('.').str[0]
            scheduler['Status'] = scheduler['Status'].astype(str).str.upper().str.strip()
            scheduler['VotedDate'] = scheduler['VotedDate'].astype(str).str.strip()

            provider['Individual NPI'] = provider['Individual NPI'].astype(str).str.strip().str.split('.').str[0]
            provider['Provider Effective Date'] = provider['Provider Effective Date'].astype(str).str.strip()

            def parse_flexible_date(val):
                val = val.strip()
                if not val or val.lower() in {"blank data", "no data", "nan"}:
                    return None
                try:
                    return parser.parse(val, dayfirst=False, yearfirst=False)
                except (ValueError, OverflowError):
                    return None

            scheduler['ParsedDateObj'] = scheduler['VotedDate'].apply(parse_flexible_date)
            scheduler['Mapped Date'] = scheduler.apply(
                lambda r: r['ParsedDateObj'].strftime('%d-%m-%Y')
                if (r['Status'] == 'APPROVED' and r['ParsedDateObj'] is not None)
                else None,
                axis=1
            )

            # Create a dictionary: NPI → Mapped Date
            npi_to_date = scheduler.set_index('NPI')['Mapped Date'].dropna().to_dict()

            def fill_provider(row):
                cur = row['Provider Effective Date']
                key = row['Individual NPI']
                if not cur or cur.lower() in {"blank data", "no data", "nan"}:
                    return npi_to_date.get(key, "")
                return cur

            provider['Provider Effective Date'] = provider.apply(fill_provider, axis=1)

            # Generate updated Excel for download
            out = BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as w:
                provider.to_excel(w, index=False)
            out.seek(0)

            resp = HttpResponse(out,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            resp['Content-Disposition'] = 'attachment; filename="updated_providers.xlsx"'
            return resp

        except Exception as e:
            traceback.print_exc()
            return render(request, 'uploader/upload.html',
                          {'error': f"An error occurred: {e}"})

    return render(request, 'uploader/upload.html')
