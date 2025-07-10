from django import forms

class UploadFileForm(forms.Form):
    datafile = forms.FileField(label="로그 CSV 파일 업로드")
    def clean_datafile(self):
        file = self.cleaned_data.get('datafile')
        if not file.name.endswith('.csv'):
            raise forms.ValidationError("CSV 파일만 업로드할 수 있습니다.")
        return file