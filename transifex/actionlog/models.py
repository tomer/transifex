import datetime
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import smart_unicode
from django.utils.encoding import force_unicode
from django.shortcuts import get_object_or_404
from django.template import loader, Context, TemplateDoesNotExist
from django.utils.translation import get_language, activate
from notification.models import NoticeType

def _get_formatted_message(label, context):
    """
    Return a message that is a rendered template with the given context using 
    the default language of the system.
    """
    current_language = get_language()

    # Setting the environment to the default language
    activate(settings.LANGUAGE_CODE)

    c = Context(context)
    try:
        msg = loader.get_template('notification/%s/notice.html' % label).render(c)
    except TemplateDoesNotExist:
        #TODO: Maybe send an alert to the admins
        msg = None

    # Reset environment to original language
    activate(current_language)

    return msg

class LogEntryManager(models.Manager):
    def by_object(self, obj):
        """Return LogEntries for a related object."""
        ctype = ContentType.objects.get_for_model(obj)
        return self.filter(content_type__pk=ctype.pk, object_id=obj.pk)

    def for_projects_by_user(self, user):
        """Return project LogEntries for a related user."""
        ctype = ContentType.objects.get(model='project')
        return self.filter(user__pk__exact=user.pk, content_type__pk=ctype.pk)

class LogEntry(models.Model):
    """A Entry in an object's log."""
    user = models.ForeignKey(User, blank=True, null=True, 
                             related_name="tx_user_action")

    object_id = models.IntegerField(blank=True, null=True)
    content_type = models.ForeignKey(ContentType, blank=True, null=True,
                                     related_name="tx_object")

    action_type = models.ForeignKey(NoticeType)
    action_time = models.DateTimeField()
    object_name = models.CharField(blank=True, max_length=200)
    message = models.TextField(blank=True, null=True)

    # Managers
    objects = LogEntryManager()
    
    class Meta:
        verbose_name = _('log entry')
        verbose_name_plural = _('log entries')
        ordering = ('-action_time',)

    def __unicode__(self):
        return u'%s.%s.%s' % (self.action_type, self.object_name, self.user)

    def __repr__(self):
        return smart_unicode("<LogEntry %d (%s)>" % (self.id,
                                                     self.action_type.label))

    def save(self, *args, **kwargs):
        """Save the object in the database."""
        if self.action_time is None:
           self.action_time = datetime.datetime.now()
        super(LogEntry, self).save(*args, **kwargs)

    def message_safe(self):
        """Return the message as HTML"""
        return self.message
    message_safe.allow_tags = True
    message_safe.admin_order_field = 'message'

    @property
    def action_type_short(self):
        """
        Return a shortened, generalized version of an action type.
        
        Useful for presenting an image signifying an action type. Example::
        
        >>> print l.action_type
        <NoticeType: project_component_added>
        >>> print l.action_type_short
        u'added'
        """
        return self.action_type.label.split('_')[-1]

def action_logging(user, object_list, action_type, message=None, context=None):
    """
    Add ActionLog using a set of parameters.
    
    user:
      The user that did the action.
    object_list:
      A list of objects that should be created the actionlog for.
    action_type:
      Label of a type of action from the NoticeType model.
    message:
      A message to be included at the actionlog. If no message is passed
      it will try do render a message using the notice.html from the
      notification application.
    context:
      To render the message using the notification files, sometimes it is 
      necessary to pass some vars by using a context.

    Usage::

        al = 'project_component_added'
        context = {'component': object}
        action_logging(request.user, [object], al , context=context):
    """

    if context is None:
        context = {}

    if message is None:
        message = _get_formatted_message(action_type, context)

    action_type_obj = get_object_or_404(NoticeType, label=action_type)

    time = datetime.datetime.now()

    try:
        for object in object_list:
            l = LogEntry(
                    user_id = user.pk, 
                    content_type = ContentType.objects.get_for_model(object),
                    object_id = object.pk,
                    object_name = force_unicode(object)[:200], 
                    action_type = action_type_obj,
                    action_time = time,
                    message = message)
            l.save()
    except TypeError:
        raise TypeError("The 'object_list' parameter must be iterable")
