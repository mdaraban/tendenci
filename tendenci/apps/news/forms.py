import imghdr
from os.path import splitext, basename
from datetime import datetime

from django import forms
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.template.defaultfilters import filesizeformat
from django.conf import settings

from tendenci.apps.news.models import News
from tendenci.apps.perms.forms import TendenciBaseForm
from tendenci.libs.tinymce.widgets import TinyMCE
from tendenci.apps.base.fields import SplitDateTimeField
from tendenci.apps.base.fields import EmailVerificationField
from tendenci.apps.files.utils import get_max_file_upload_size
from tendenci.apps.perms.utils import get_query_filters
from tendenci.apps.site_settings.utils import get_setting
from tendenci.apps.user_groups.models import Group

ALLOWED_LOGO_EXT = (
    '.jpg',
    '.jpeg',
    '.gif',
    '.png'
)

CONTRIBUTOR_CHOICES = (
    (News.CONTRIBUTOR_AUTHOR, mark_safe('Author <i class="gauthor-info fa fa-lg fa-question-circle"></i>')),
    (News.CONTRIBUTOR_PUBLISHER, mark_safe('Publisher <i class="gpub-info fa fa-lg fa-question-circle"></i>'))
)
GOOGLE_PLUS_HELP_TEXT = 'Additional Options for Authorship <i class="gauthor-help fa fa-lg fa-question-circle"></i><br>Additional Options for Publisher <i class="gpub-help fa fa-lg fa-question-circle"></i>'


class NewsForm(TendenciBaseForm):
    body = forms.CharField(required=False,
        widget=TinyMCE(attrs={'style': 'width:100%;'},
        mce_attrs={'storme_app_label': News._meta.app_label,
        'storme_model': News._meta.model_name.lower()}))
    release_dt = SplitDateTimeField(label=_('Release Date/Time'), initial=datetime.now())
    status_detail = forms.ChoiceField(
        choices=(('active', _('Active')), ('inactive', _('Inactive')), ('pending', _('Pending'))))
    email = EmailVerificationField(label=_("Email"), required=False)
    syndicate = forms.BooleanField(label=_('Include in RSS Feed'), required=False, initial=True)

    contributor_type = forms.ChoiceField(choices=CONTRIBUTOR_CHOICES,
                                         initial=News.CONTRIBUTOR_AUTHOR,
                                         widget=forms.RadioSelect())

    photo_upload = forms.FileField(label=_('Thumbnail Image'), required=False, help_text=_('The thumbnail image can be used on your homepage or sidebar if it is setup in your theme. It will not display on the news page.'))
    remove_photo = forms.BooleanField(label=_('Remove the current photo'), required=False)

    group = forms.ChoiceField(required=True, choices=[])

    class Meta:
        model = News

        fields = (
        'headline',
        'slug',
        'summary',
        'body',
        'group',
        'photo_upload',
        'source',
        'website',
        'release_dt',
        'timezone',
        'contributor_type',
        'first_name',
        'last_name',
        'google_profile',
        'phone',
        'fax',
        'email',
        'tags',
        'allow_anonymous_view',
        'syndicate',
        'user_perms',
        'member_perms',
        'group_perms',
        'status_detail',
        )

        fieldsets = [(_('News Information'), {
                      'fields': ['headline',
                                 'slug',
                                 'summary',
                                 'body',
                                 'group',
                                 'tags',
                                 'photo_upload',
                                 'source',
                                 'website',
                                 'release_dt',
                                 'timezone',
                                 ],
                      'legend': ''
                      }),
                      (_('Contributor'), {
                       'fields': ['contributor_type',
                                  'google_profile'],
                       'classes': ['boxy-grey'],
                      }),
                      (_('Author'), {
                      'fields': ['first_name',
                                 'last_name',
                                 'phone',
                                 'fax',
                                 'email',
                                 ],
                        'classes': ['contact'],
                      }),
                      (_('Permissions'), {
                      'fields': ['allow_anonymous_view',
                                 'user_perms',
                                 'member_perms',
                                 'group_perms',
                                 ],
                      'classes': ['permissions'],
                      }),
                     (_('Administrator Only'), {
                      'fields': ['syndicate',
                                 'status_detail'],
                      'classes': ['admin-only'],
                    })]

    def clean_photo_upload(self):
        photo_upload = self.cleaned_data['photo_upload']
        if photo_upload:
            extension = splitext(photo_upload.name)[1]

            # check the extension
            if extension.lower() not in ALLOWED_LOGO_EXT:
                raise forms.ValidationError(_('The photo must be of jpg, gif, or png image type.'))

            # check the image header
            image_type = '.%s' % imghdr.what('', photo_upload.read())
            if image_type not in ALLOWED_LOGO_EXT:
                raise forms.ValidationError(_('The photo is an invalid image. Try uploading another photo.'))

            max_upload_size = get_max_file_upload_size()
            if photo_upload.size > max_upload_size:
                raise forms.ValidationError(_('Please keep filesize under %(max_upload_size)s. Current filesize %(upload_size)s') % {
                                            'max_upload_size': filesizeformat(max_upload_size),
                                            'upload_size': filesizeformat(photo_upload.size)})

        return photo_upload

    def clean_group(self):
        group_id = self.cleaned_data['group']

        try:
            group = Group.objects.get(pk=group_id)
            return group
        except Group.DoesNotExist:
            raise forms.ValidationError(_('Invalid group selected.'))

    def clean_syndicate(self):
        """
        clean method for syndicate added due to the update
        done on the field BooleanField -> NullBooleanField
        NOTE: BooleanField is converted to NullBooleanField because
        some Boolean data has value of None than False. This was updated
        on Django 1.6. BooleanField cannot have a value of None.
        """
        data = self.cleaned_data.get('syndicate', False)
        if data:
            return True
        else:
            return False

    def save(self, *args, **kwargs):
        news = super(NewsForm, self).save(*args, **kwargs)
        if self.cleaned_data.get('remove_photo'):
            news.thumbnail = None
        return news

    def __init__(self, *args, **kwargs):
        super(NewsForm, self).__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['body'].widget.mce_attrs['app_instance_id'] = self.instance.pk
        else:
            self.fields['body'].widget.mce_attrs['app_instance_id'] = 0
            self.fields['group'].initial = Group.objects.get_initial_group_id()

        default_groups = Group.objects.filter(status=True, status_detail="active")

        #if not self.user.profile.is_superuser:
        if self.user and not self.user.profile.is_superuser:
            if 'status_detail' in self.fields:
                self.fields.pop('status_detail')

            filters = get_query_filters(self.user, 'user_groups.view_group', **{'perms_field': False})
            groups = default_groups.filter(filters).distinct()
            groups_list = list(groups.values_list('pk', 'name'))

            users_groups = self.user.profile.get_groups()
            for g in users_groups:
                if [g.id, g.name] not in groups_list:
                    groups_list.append([g.id, g.name])
        else:
            groups_list = default_groups.values_list('pk', 'name')

        self.fields['group'].choices = groups_list
        self.fields['google_profile'].help_text = mark_safe(GOOGLE_PLUS_HELP_TEXT)
        self.fields['timezone'].initial = settings.TIME_ZONE

        # only show the remove photo checkbox if there is already a thumbnail
        if self.instance.thumbnail:
            self.fields['photo_upload'].help_text = '<input name="remove_photo" id="id_remove_photo" type="checkbox"/> Remove current image: <a target="_blank" href="/files/%s/">%s</a>' % (self.instance.thumbnail.pk, basename(self.instance.thumbnail.file.name))
        else:
            self.fields.pop('remove_photo')
