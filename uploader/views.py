from django.shortcuts import render
from django.http import HttpResponse
import pandas as pd
from io import BytesIO


def home(request):
    if request.method == 'POST' and request.FILES:
        try:
            # Get uploaded files
            scheduler_file = request.FILES['Scheduler mhc']
            provider_file = request.FILES['Roaster_mhc']

            # Read Excel files
            scheduler = pd.read_excel(scheduler_file) 
            provider = pd.read_excel(provider_file)

            # Process data - only approved status (case insensitive)
            approved = scheduler[scheduler['Status'].str.upper() == 'APPROVED'].copy()
            
            # Convert NPI to string and strip any whitespace for proper matching
            approved['NPI'] = approved['NPI'].astype(str).str.strip()
            provider['Individual NPI'] = provider['Individual NPI'].astype(str).str.strip()
            
            # Create mapping of NPI to VotedDate
            npi_to_voteddate = approved.set_index('NPI')['VotedDate'].to_dict()
            
            # Update provider data - only update where NPI matches
            provider['Provider Effective Date'] = provider['Individual NPI'].map(npi_to_voteddate)
            
            # Prepare output
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                provider.to_excel(writer, index=False)
            output.seek(0)

            # Return processed file as download
            response = HttpResponse(
                output,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="updated_providers.xlsx"'
            return response
            
        except Exception as e:
            error_message = f"Error processing files: {str(e)}"
            return render(request, 'uploader/upload.html', {'error': error_message})


    return render(request, 'uploader/upload.html')