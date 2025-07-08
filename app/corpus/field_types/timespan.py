import calendar
import mongoengine
from ..utilities import parse_date_string


class Timespan(mongoengine.EmbeddedDocument):
    start = mongoengine.DateTimeField()
    end = mongoengine.DateTimeField()
    uncertain = mongoengine.BooleanField()
    granularity = mongoengine.StringField(choices=('Year', 'Month', 'Day', 'Time'))

    def normalize(self):
        if self.start and self.granularity and self.granularity not in ['Time']:
            start_year = self.start.year
            start_month = self.start.month
            start_day = self.start.day

            end_year = self.end.year if self.end else start_year
            end_month = self.end.month if self.end else start_month
            end_day = self.end.day if self.end else start_day

            if self.granularity in ['Month', 'Year']:
                start_day = 1

                if self.granularity == 'Year':
                    start_month = 1
                    end_month = 12

                end_day = calendar.monthrange(end_year, end_month)[1]

            self.start = parse_date_string(f"{start_year}-{start_month}-{start_day} 00:00")
            self.end = parse_date_string(f"{end_year}-{end_month}-{end_day} 23:59")

    @property
    def string_representation(self):
        if self.start:
            time_format_string = '%Y-%m-%d %H:%M'

            if self.granularity == 'Year':
                time_format_string = '%Y'
            elif self.granularity == 'Month':
                time_format_string = '%B %Y'
            elif self.granularity == 'Day':
                time_format_string = '%Y-%m-%d'

            start_date = self.start.strftime(time_format_string)
            formatted_value = start_date

            if self.end:
                end_date = self.end.strftime(time_format_string)
                formatted_value = f'{start_date} to {end_date}'

            if self.uncertain == 'true':
                formatted_value = f'Around {formatted_value}'

            return formatted_value
        return ''

    def to_dict(self, parent_uri=None):
        start_dt = None
        if self.start:
            start_dt = self.start.isoformat()

            end_dt = None
            if self.end:
                end_dt = self.end.isoformat()

            return {
                'start': start_dt,
                'end': end_dt,
                'uncertain': self.uncertain,
                'granularity': self.granularity
            }
        return None