from django.db import models
from django.db.models import Max, Sum

from cms.models import CMSPlugin
from cms.models.fields import PageField
from taggit.managers import TaggableManager
from django.contrib.auth.models import Group
from autoslug import AutoSlugField
from django.contrib import admin


class Quiz(CMSPlugin):
    title = models.CharField(max_length=255)
    slug = AutoSlugField(populate_from='title')
    group = models.ForeignKey(Group, related_name="quizzes")
    created_dt = models.DateTimeField(auto_now=True)
    help_text = models.TextField(blank=True, null=True)
    page_hook = PageField(blank=True, null=True)
    must_complete = models.BooleanField(help_text="Check this box if you want the user to get each question correct before proceeding.")

    def __unicode__(self):
        return u"%s" % self.title

    def free_text_questions(self, user):
        questions = self.questions.filter(question_type='F')
        subs = []
        for q in questions:
            try:
                subs.append(Submission.objects.get(question=q, user=user))
            except:
                pass
        return subs

    def percent_score(self, user):
        score = 0
        tot_score = 0
        for question in self.questions.exclude(question_type='F'):
            score += Submission.objects.get(question=question, user=user).score
            tot_score += question.max_score
        if tot_score != 0:
            return round(100 * float(score) / tot_score, 2)
        else:
            return 0

    def avg_tries(self, user):
    #for must completes, returns a list of tries and avg. tries per question.
        tries = 0
        for q in self.questions.exclude(question_type='F'):
            tries += Submission.objects.get(question=q, user=user).tries + 1
        return round(float(tries) / self.questions.exclude(question_type='F').count(), 1)

    def scores_list(self, user):
        q_list = []
        for question in self.questions.exclude(question_type='F'):
            q = {}
            if not self.must_complete:
                q['title'] = question.title
                q['score'] = question.percent_score_for_user(user)
            else:
                q['title'] = question.title
                q['tries'] = user.saq_submissions.get(question=question).tries
            q_list.append(q)
        return q_list


class HelpText(models.Model):
    title = models.CharField(max_length=255)
    created_dt = models.DateTimeField(auto_now=True)
    slug = AutoSlugField(populate_from='title')
    help_text = models.TextField(blank=True, null=True)
    question = models.ForeignKey('cms_saq.Question', related_name="help_info")

    def __unicode__(self):
        return u"%s" % self.title


class Answer(models.Model):
    title = models.CharField(max_length=255)
    slug = AutoSlugField(populate_from='title')
    help_text = models.TextField(blank=True, null=True)
    score = models.IntegerField(default=0)
    question = models.ForeignKey('cms_saq.Question', related_name="answers")

    def __unicode__(self):
        return u"%s" % self.title


class GroupedAnswer(Answer):
    group = models.CharField(max_length=255)


class Question(CMSPlugin):
    QUESTION_TYPES = [
        ('S', 'Single-choice question'),
        ('M', 'Multi-choice question'),
        ('F', 'Free-text question'),
    ]
    title = models.CharField(max_length=3000, help_text="Question to be answered by student.")
    slug = AutoSlugField(populate_from='title')
    tags = TaggableManager(blank=True)
    label = models.CharField(max_length=255, blank=True)
    help_text = models.CharField(max_length=255, blank=True)
    question_type = models.CharField(max_length=1, choices=QUESTION_TYPES)
    quiz_slug = models.ForeignKey(Quiz, blank=True, null=True, related_name='questions')

    optional = models.BooleanField(
        default=False,
        help_text="Only applies to free text questions",
    )

    def score(self, answers):
        if self.question_type == 'F':
            return 0
        elif self.question_type == 'S':
            return self.answers.get(slug=answers).score
        elif self.question_type == 'M':
            answers_list = answers.split(',')
            return sum([self.answers.get(slug=a).score for a in answers_list])

    @property
    def max_score(self):
        if not hasattr(self, '_max_score'):
            if self.question_type == "S":
                self._max_score = self.answers.aggregate(Max('score'))['score__max']
            elif self.question_type == "M":
                self._max_score = self.answers.filter(score__gt=0).aggregate(Sum('score'))['score__sum']
            else:
                self._max_score = None # don't score free-text answers
        return self._max_score

    def percent_score_for_user(self, user):
        if self.max_score:
            try:
                score = Submission.objects.get(question=self, user=user).score
            except Submission.DoesNotExist:
                return 0
            return 100.0 * score / self.max_score
        else:
            return 0

    def __unicode__(self):
        return self.title


class Submission(models.Model):
    question = models.ForeignKey(Question, blank=True, null=True)
    answer = models.TextField(blank=True)
    score = models.IntegerField()
    user = models.ForeignKey('auth.User', related_name='saq_submissions')
    tries = models.IntegerField(default=0)

    class Meta:
        ordering = ('user', 'question')
        unique_together = ('question', 'user')

    def answer_list(self):
        return self.answer.split(",")

    def __unicode__(self):
        return u"%s answer to %s" % (self.user, self.question)


class Completion(models.Model):
    quiz = models.ForeignKey(Quiz, related_name='completed')
    user = models.ForeignKey('auth.User', related_name='saq_completions')
    created_dt = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return u"%s completed %s" % (self.user, self.quiz)


class FormNav(CMSPlugin):
    next_page = PageField(blank=True, null=True, related_name="formnav_nexts")
    next_page_label = models.CharField(max_length=255, blank=True, null=True)
    prev_page = PageField(blank=True, null=True, related_name="formnav_prevs")
    prev_page_label = models.CharField(max_length=255, blank=True, null=True)
    end_page = PageField(blank=True, null=True, related_name="formnav_ends")
    end_page_label = models.CharField(max_length=255, blank=True, null=True)
    end_page_condition_question = models.ForeignKey(Question, null=True, blank=True)


class SectionedScoring(CMSPlugin):
    def scores_for_user(self, user):
        scores = [[s.label, s.score_for_user(user)] for s in self.sections.all()]
        overall = sum([s[1] for s in scores]) / len(scores)
        return [scores, overall]


class ScoreSection(models.Model):
    group = models.ForeignKey('cms_saq.SectionedScoring', related_name='sections')
    label = models.CharField(max_length=255)
    tag = models.CharField(max_length=255)
    order = models.IntegerField()

    class Meta:
        ordering = ('order', 'label')

    def score_for_user(self, user):
        return aggregate_score_for_user_by_tags(user, [self.tag])


def aggregate_score_for_user_by_tags(user, tags):
    questions = Question.objects.filter(tags__name__in=tags).distinct()
    scores = []
    for question in questions:
        score = question.percent_score_for_user(user)
        if score is not None:
            scores.append(score)
    if len(scores):
        return sum(scores) / len(scores)
    else:
        return 0


admin.site.register(Completion)
admin.site.register(Submission)
