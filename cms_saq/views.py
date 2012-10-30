import re

from django.template.loader import render_to_string
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.cache import never_cache
from django.utils import simplejson
from django.conf import settings

from cms_saq.models import Question, Answer, Submission, HelpText, Completion, Quiz

ANSWER_RE = re.compile(r'^[\w-]+(,[\w-]+)*$')


@require_POST
def _submit(request):
    results = {'score': 0}
    for question_slug, answers in request.POST.iteritems():
        # validate the question
        try:
            question = Question.objects.get(slug=question_slug)
        except Question.DoesNotExist:
            return HttpResponseBadRequest("Invalid question '%s'" % question_slug)
        try:
            quiz_page = question.page.parent
            quiz = Quiz.objects.get(page_hook=quiz_page)
        except Question.DoesNotExist:
            return HttpResponseBadRequest("Invalid question '%s'" % question_slug)
        # check answers is a list of slugs
        if question.question_type != 'F' and not ANSWER_RE.match(answers):
            return HttpResponseBadRequest("Invalid answers: %s" % answers)
        # validate and score the answer
        try:
            score = question.score(answers)
            results['score'] += score
            ##this is for quizzes where you cannot proceed without getting correct answer
            if ((score == question.max_score or question.max_score == None) and quiz.must_complete) or not quiz.must_complete:
                results['complete'] = True
            else:
                results['complete'] = False
                results['error'] = render_to_string('quiz/error.html', {'error': 'Your reponse is incorrect. Please try again.'})
        except Answer.DoesNotExist:
            return HttpResponseBadRequest("Invalid answer '%s:%s'" % (question_slug, answers))
        # save!
        filter_attrs = {'user': request.user, 'question': question}
        attrs = {'answer': answers, 'score': score}
        rows = Submission.objects.filter(**filter_attrs).update(**attrs)
        #create if doesn't exist, update # of tries
        if not rows:
            filter_attrs['tries'], tries = 0, 0
            attrs.update(filter_attrs)
            Submission.objects.create(**attrs)
        else:
            s = Submission.objects.get(**filter_attrs)
            s.tries += 1
            tries = s.tries
            s.save()
        ### check if this quiz is completed, ignore staff
        if not request.user.is_staff:
        ##### if this is not must_complete, just require num submissions equal to questions
            if question.quiz_slug.questions.count() == request.user.saq_submissions.filter(question__quiz_slug=quiz).count():
                if not quiz.must_complete:
                    Completion.objects.get_or_create(user=request.user, quiz=question.quiz_slug)
                elif results['complete']:
                    Completion.objects.get_or_create(user=request.user, quiz=question.quiz_slug)
        ht = HelpText.objects.filter(question=question).order_by('created_dt')
        if ht.count() > 0:
            ht_data = [{'text': i.help_text, 'title': i.title} for i in ht[0: min(ht.count(), tries)]]
            rendered = render_to_string('quiz/help_info.html', {'help_text': ht_data})
            results['help_text'] = rendered
    return HttpResponse(simplejson.dumps(results),
                    mimetype='application/json')

if getattr(settings, "SAQ_LAZYSIGNUP", False):
    from lazysignup.decorators import allow_lazy_user
    submit = allow_lazy_user(_submit)
else:
    submit = login_required(_submit)


@require_GET
@never_cache
@login_required
def scores(request):
    slugs = request.GET.getlist('q')
    if slugs == []:
        return HttpResponseBadRequest("No questions supplied")
    submissions = Submission.objects.filter(user=request.user, question__in=slugs)
    submissions = [[s.question, {'answer': s.answer, 'score': s.score}]
            for s in submissions]
    data = {
        "questions": slugs,
        "submissions": dict(submissions),
        "complete": len(submissions) == len(slugs)
    }
    return HttpResponse(simplejson.dumps(data), mimetype="application/json")

# TODO benchmarking

