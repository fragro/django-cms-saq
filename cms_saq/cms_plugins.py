import itertools, operator

from django.contrib import admin

from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool

from cms_saq.models import Question, Answer, GroupedAnswer, Submission, \
        FormNav, SectionedScoring, ScoreSection, Quiz, HelpText, Completion


class AnswerAdmin(admin.StackedInline):
    model = Answer
    extra = 0
    verbose_name = "answer"


class HelpTextAdmin(admin.StackedInline):
    model = HelpText
    extra = 0
    verbose_name = "help text"


class QuizPlugin(CMSPluginBase):
    model = Quiz
    module = "SAQ"
    name = "Quiz"
    render_template = "cms_saq/quiz.html"
    exclude = ('page_hook',)

    def render(self, context, instance, placeholder):
        user = context['request'].user
        extra = {
            'quiz': instance,
            'children': Question.objects.filter(quiz_slug=instance)
        }
        context.update(extra)
        return context

    def save_model(self, request, obj, form, change):
        obj.page_hook = request.current_page
        obj.save()


class NoHelpTextAnswerAdmin(AnswerAdmin):
    exclude = ('help_text',)


class NoHelpTextGroupedAnswerAdmin(NoHelpTextAnswerAdmin):
    model = GroupedAnswer


class QuestionPlugin(CMSPluginBase):
    model = Question
    module = "SAQ"
    inlines = [AnswerAdmin, HelpTextAdmin]
    exclude = ('question_type',)

    def render(self, context, instance, placeholder):
        user = context['request'].user
        current_page = context['request'].current_page
        questions = current_page.parent.children.all()
        extra = {
            'question': instance,
            'answers': instance.answers.all(),
            'width': str(int(((list(questions).index(current_page)) / float(questions.count())) * 100)) + '%'
        }
        if user.is_authenticated():
            try:
                extra['submission'] = Submission.objects.get(user=user, question=instance)
            except Submission.DoesNotExist:
                pass
        context.update(extra)
        return context

    def save_model(self, request, obj, form, change):
        obj.question_type = self.question_type
        #doesn't work in EDIT mode??? TODO
        if obj.quiz_slug == None:
            p = request.current_page.parent
            q = Quiz.objects.get(page_hook=p)
            obj.quiz_slug = q
        obj.save()


class SingleChoiceQuestionPlugin(QuestionPlugin):
    name = "Single Choice Question"
    render_template = "cms_saq/single_choice_question.html"
    question_type = "S"
    exclude = ('question_type', 'label', 'help_text', 'quiz_slug',)


class MultiChoiceQuestionPlugin(QuestionPlugin):
    name = "Multi Choice Question"
    render_template = "cms_saq/multi_choice_question.html"
    question_type = "M"
    exclude = ('question_type', 'label', 'help_text', 'quiz_slug',)


class DropDownQuestionPlugin(QuestionPlugin):
    name = "Drop-down Question"
    render_template = "cms_saq/drop_down_question.html"
    inlines = [NoHelpTextAnswerAdmin]
    question_type = "S"
    exclude = ('quiz_slug', 'question_type', 'label', )


class GroupedDropDownQuestionPlugin(QuestionPlugin):
    name = "Grouped Drop-down Question"
    render_template = "cms_saq/drop_down_question.html"
    inlines = [NoHelpTextGroupedAnswerAdmin]
    question_type = "S"
    exclude = ('quiz_slug', 'question_type', 'label', )

    def render(self, context, instance, placeholder):
        new_ctx = super(GroupedDropDownQuestionPlugin, self).render(context, instance, placeholder)
        answers = list(GroupedAnswer.objects.filter(question=instance))
        grouped_answers = itertools.groupby(answers, operator.attrgetter('group'))
        grouped_answers = [[key, list(group)] for key, group in grouped_answers]
        new_ctx.update({'grouped_answers': grouped_answers})
        return new_ctx


class FreeTextQuestionPlugin(QuestionPlugin):
    name = "Free Text Question"
    render_template = "cms_saq/free_text_question.html"
    inlines = []
    question_type = "F"
    exclude = ('quiz_slug', 'question_type', 'label', )


class FormNavPlugin(CMSPluginBase):
    model = FormNav
    name = "Back / Next Buttons"
    module = "SAQ"
    render_template = "cms_saq/form_nav.html"

    def render(self, context, instance, placeholder):
        met_end_condition = False
        if instance.end_page_condition_question:
            end_condition_slug = instance.end_page_condition_question.slug
            met_end_condition = (Submission.objects
                .filter(user=context['user'], question=end_condition_slug)
                .count()) > 0
        context.update({
            'instance': instance,
            'met_end_condition': met_end_condition
        })
        return context


class ScoreSectionAdmin(admin.TabularInline):
    model = ScoreSection
    extra = 0
    verbose_name = "section"


class SectionedScoringPlugin(CMSPluginBase):
    model = SectionedScoring
    name = "Sectioned Scoring"
    module = "SAQ"
    render_template = "cms_saq/sectioned_scoring.html"
    inlines = [ScoreSectionAdmin]

    def render(self, context, instance, placeholder):
        scores, overall = instance.scores_for_user(context['request'].user)
        context.update({
            'scores': scores,
            'overall': overall
        })
        return context

plugin_pool.register_plugin(SingleChoiceQuestionPlugin)
plugin_pool.register_plugin(MultiChoiceQuestionPlugin)
plugin_pool.register_plugin(DropDownQuestionPlugin)
plugin_pool.register_plugin(GroupedDropDownQuestionPlugin)
plugin_pool.register_plugin(FreeTextQuestionPlugin)
plugin_pool.register_plugin(QuizPlugin)

