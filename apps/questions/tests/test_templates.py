import json

from django.contrib.auth.models import User, Permission

from nose.tools import eq_
from pyquery import PyQuery as pq

from sumo.urlresolvers import reverse
from sumo.helpers import urlparams
from questions.models import Question, Answer, QuestionVote
from questions.tests import (TestCaseBase, TaggingTestCaseBase, post, get,
                             tags_eq)
from questions.views import UNAPPROVED_TAG, NO_TAG


class AnswersTemplateTestCase(TestCaseBase):
    """Test the Answers template."""
    def setUp(self):
        super(AnswersTemplateTestCase, self).setUp()

        self.client.login(username='jsocol', password='testpass')
        self.question = Question.objects.all()[0]
        self.answer = self.question.answers.all()[0]

    def tearDown(self):
        super(AnswersTemplateTestCase, self).tearDown()

        self.client.logout()

    def test_answer(self):
        """Posting a valid answer inserts it."""
        num_answers = self.question.answers.count()
        content = 'lorem ipsum dolor sit amet'
        response = post(self.client, 'questions.reply',
                        {'content': content},
                        args=[self.question.id])

        eq_(1, len(response.redirect_chain))
        eq_(num_answers + 1, self.question.answers.count())

        new_answer = self.question.answers.order_by('-created')[0]
        eq_(content, new_answer.content)

    def test_empty_answer(self):
        """Posting an empty answer shows error."""
        response = post(self.client, 'questions.reply', {'content': ''},
                        args=[self.question.id])

        doc = pq(response.content)
        error_msg = doc('ul.errorlist li a')[0]
        eq_(error_msg.text, 'Please provide content.')

    def test_short_answer(self):
        """Posting a short answer shows error."""
        response = post(self.client, 'questions.reply', {'content': 'lor'},
                        args=[self.question.id])

        doc = pq(response.content)
        error_msg = doc('ul.errorlist li a')[0]
        eq_(error_msg.text, 'Your content is too short (3 characters). ' +
                            'It must be at least 5 characters.')

    def test_long_answer(self):
        """Post a long answer shows error."""

        # Set up content length to 10,001 characters
        content = ''
        for i in range(1000):
            content += '1234567890'
        content += '1'

        response = post(self.client, 'questions.reply', {'content': content},
                        args=[self.question.id])

        doc = pq(response.content)
        error_msg = doc('ul.errorlist li a')[0]
        eq_(error_msg.text, 'Please keep the length of your content to ' +
                            '10,000 characters or less. It is currently ' +
                            '10,001 characters.')

    def test_solution(self):
        """Test accepting a solution."""
        response = get(self.client, 'questions.answers',
                       args=[self.question.id])
        doc = pq(response.content)
        eq_(0, len(doc('div.solution')))

        answer = self.question.answers.all()[0]
        response = post(self.client, 'questions.solution',
                        args=[self.question.id, answer.id])
        doc = pq(response.content)
        eq_(1, len(doc('div.solution')))
        eq_('answer-%s' % answer.id, doc('li.solution')[0].attrib['id'])

        self.question.solution = None
        self.question.save()

    def test_only_owner_can_accept_solution(self):
        """Make sure non-owner can't mark solution."""
        response = get(self.client, 'questions.answers',
                       args=[self.question.id])
        doc = pq(response.content)
        eq_(1, len(doc('input[name="solution"]')))

        self.client.logout()
        self.client.login(username='pcraciunoiu', password='testpass')
        response = get(self.client, 'questions.answers',
                       args=[self.question.id])
        doc = pq(response.content)
        eq_(0, len(doc('input[name="solution"]')))

        answer = self.question.answers.all()[0]
        response = post(self.client, 'questions.solution',
                        args=[self.question.id, answer.id])
        eq_(403, response.status_code)

    def test_question_vote_GET(self):
        """Attempting to vote with HTTP GET returns a 405."""
        response = get(self.client, 'questions.vote',
                       args=[self.question.id])
        eq_(405, response.status_code)

    def common_vote(self):
        """Helper method for question vote tests."""
        # Check that there are no votes and vote form renders
        response = get(self.client, 'questions.answers',
                       args=[self.question.id])
        doc = pq(response.content)
        eq_('0 people', doc('div.have-problem mark')[0].text)
        eq_(1, len(doc('div.me-too form')))

        # Vote
        post(self.client, 'questions.vote', args=[self.question.id])

        # Check that there is 1 vote and vote form doesn't render
        response = get(self.client, 'questions.answers',
                       args=[self.question.id])
        doc = pq(response.content)
        eq_('1 person', doc('div.have-problem mark')[0].text)
        eq_(0, len(doc('div.me-too form')))

        # Voting again (same user) should not increment vote count
        post(self.client, 'questions.vote', args=[self.question.id])
        response = get(self.client, 'questions.answers',
                       args=[self.question.id])
        doc = pq(response.content)
        eq_('1 person', doc('div.have-problem mark')[0].text)

    def test_question_authenticated_vote(self):
        """Authenticated user vote."""
        # Common vote test
        self.common_vote()

    def test_question_anonymous_vote(self):
        """Anonymous user vote."""
        # Log out
        self.client.logout()

        # Common vote test
        self.common_vote()

    def common_answer_vote(self):
        """Helper method for answer vote tests."""
        # Check that there are no votes and vote form renders
        response = get(self.client, 'questions.answers',
                       args=[self.question.id])
        doc = pq(response.content)
        eq_('0 out of 0 people', doc('#answer-1 div.helpful mark')[0].text)
        eq_(1, len(doc('form.helpful input[name="helpful"]')))

        # Vote
        post(self.client, 'questions.answer_vote', {'helpful': 'y'},
             args=[self.question.id, self.answer.id])

        # Check that there is 1 vote and vote form doesn't render
        response = get(self.client, 'questions.answers',
                       args=[self.question.id])
        doc = pq(response.content)

        eq_('1 out of 1 person', doc('#answer-1 div.helpful mark')[0].text)
        eq_(0, len(doc('form.helpful input[name="helpful"]')))

        # Voting again (same user) should not increment vote count
        post(self.client, 'questions.answer_vote', {'helpful': 'y'},
             args=[self.question.id, self.answer.id])
        doc = pq(response.content)
        eq_('1 out of 1 person', doc('#answer-1 div.helpful mark')[0].text)

    def test_answer_authenticated_vote(self):
        """Authenticated user answer vote."""
        # log in as rrosario (didn't ask or answer question)
        self.client.logout()
        self.client.login(username='rrosario', password='testpass')

        # Common vote test
        self.common_answer_vote()

    def test_answer_anonymous_vote(self):
        """Anonymous user answer vote."""
        # Log out
        self.client.logout()

        # Common vote test
        self.common_answer_vote()

    def test_answer_score(self):
        """Test the helpful replies score."""
        self.client.logout()

        # A helpful vote
        post(self.client, 'questions.answer_vote', {'helpful': 'y'},
             args=[self.question.id, self.answer.id])

        # Verify score (should be 1)
        response = get(self.client, 'questions.answers',
                       args=[self.question.id])
        doc = pq(response.content)
        eq_('1', doc('div.other-helpful span.votes')[0].text)

        # A non-helpful vote
        self.client.login(username='rrosario', password='testpass')
        post(self.client, 'questions.answer_vote', {'not-helpful': 'y'},
             args=[self.question.id, self.answer.id])

        # Verify score (should be 0 now)
        response = get(self.client, 'questions.answers',
                       args=[self.question.id])
        doc = pq(response.content)
        eq_('0', doc('div.other-helpful span.votes')[0].text)


class TaggingViewTestsAsTagger(TaggingTestCaseBase):
    """Tests for views that add and remove tags, logged in as someone who can
    add and remove but not create tags

    Also hits the tag-related parts of the answer template.

    """
    def setUp(self):
        super(TaggingViewTestsAsTagger, self).setUp()

        # Assign can_tag permission to the "tagger" user.
        # Would be if there were a natural key for doing this via a fixture.
        self._can_tag = Permission.objects.get_by_natural_key('can_tag',
                                                              'questions',
                                                              'question')
        self._user = User.objects.get(username='tagger')
        self._user.user_permissions.add(self._can_tag)

        self.client.login(username='tagger', password='testpass')

    def tearDown(self):
        self.client.logout()
        self._user.user_permissions.remove(self._can_tag)
        super(TaggingViewTestsAsTagger, self).tearDown()

    # add_tag view:

    def test_add_tag_get_method(self):
        """Assert GETting the add_tag view redirects to the answers page."""
        response = self.client.get(_add_tag_url())
        url = 'http://testserver%s' % reverse('questions.answers',
                                              kwargs={'question_id': 1})
        self.assertRedirects(response, url)

    def test_add_nonexistent_tag(self):
        """Assert adding a nonexistent tag sychronously shows an error."""
        response = self.client.post(_add_tag_url(),
                                    data={'tag-name': 'nonexistent tag'})
        self.assertContains(response, UNAPPROVED_TAG)

    def test_add_existent_tag(self):
        """Test adding a tag, case insensitivity, and space stripping."""
        response = self.client.post(_add_tag_url(),
                                    data={'tag-name': ' PURplepurplepurple '},
                                    follow=True)
        self.assertContains(response, 'purplepurplepurple')

    def test_add_no_tag(self):
        """Make sure adding a blank tag shows an error message."""
        response = self.client.post(_add_tag_url(),
                                    data={'tag-name': ''})
        self.assertContains(response, NO_TAG)

    # add_tag_async view:

    def test_add_async_nonexistent_tag(self):
        """Assert adding an nonexistent tag yields an AJAX error."""
        response = self.client.post(_add_async_tag_url(),
                                    data={'tag-name': 'nonexistent tag'},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response, UNAPPROVED_TAG, status_code=400)

    def test_add_async_existent_tag(self):
        """Assert adding an unapplied tag yields an AJAX error."""
        response = self.client.post(_add_async_tag_url(),
                                    data={'tag-name': ' PURplepurplepurple '},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response, 'canonicalName')
        eq_([t.name for t in Question.objects.get(pk=1).tags.all()],
            ['purplepurplepurple'])  # Test the backend since we don't have a
                                     # newly rendered page to rely on.

    def test_add_async_no_tag(self):
        """Assert adding an empty tag asynchronously yields an AJAX error."""
        response = self.client.post(_add_async_tag_url(),
                                    data={'tag-name': ''},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response, NO_TAG, status_code=400)

    # remove_tag view:

    def test_remove_applied_tag(self):
        """Assert removing an applied tag succeeds."""
        response = self.client.post(_remove_tag_url(),
                                    data={'remove-tag-colorless': 'dummy'})
        self._assertRedirectsToQuestion2(response)
        eq_([t.name for t in Question.objects.get(pk=2).tags.all()], ['green'])

    def test_remove_unapplied_tag(self):
        """Test removing an unapplied tag fails silently."""
        response = self.client.post(_remove_tag_url(),
                                    data={'remove-tag-lemon': 'dummy'})
        self._assertRedirectsToQuestion2(response)

    def test_remove_no_tag(self):
        """Make sure removing with no params provided redirects harmlessly."""
        response = self.client.post(_remove_tag_url(),
                                    data={})
        self._assertRedirectsToQuestion2(response)

    def _assertRedirectsToQuestion2(self, response):
        url = 'http://testserver%s' % reverse('questions.answers',
                                              kwargs={'question_id': 2})
        self.assertRedirects(response, url)

    # remove_tag_async view:

    def test_remove_async_applied_tag(self):
        """Assert taking a tag off a question works."""
        response = self.client.post(_remove_async_tag_url(),
                                    data={'name': 'colorless'},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        eq_(response.status_code, 200)
        eq_([t.name for t in Question.objects.get(pk=2).tags.all()], ['green'])

    def test_remove_async_unapplied_tag(self):
        """Assert trying to remove a tag that isn't there succeeds."""
        response = self.client.post(_remove_async_tag_url(),
                                    data={'name': 'lemon'},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        eq_(response.status_code, 200)

    def test_remove_async_no_tag(self):
        """Assert calling the remove handler with no param fails."""
        response = self.client.post(_remove_async_tag_url(),
                                    data={},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response, NO_TAG, status_code=400)


class TaggingViewTestsAsAdmin(TaggingTestCaseBase):
    """Tests for views that create new tags, logged in as someone who can"""

    def setUp(self):
        super(TaggingViewTestsAsAdmin, self).setUp()
        self.client.login(username='admin', password='testpass')

    def tearDown(self):
        self.client.logout()
        super(TaggingViewTestsAsAdmin, self).tearDown()

    def test_add_new_tag(self):
        """Assert adding a nonexistent tag sychronously creates & adds it."""
        self.client.post(_add_tag_url(), data={'tag-name': 'nonexistent tag'})
        tags_eq(Question.objects.get(pk=1), ['nonexistent tag'])

    def test_add_async_new_tag(self):
        """Assert adding an nonexistent tag creates & adds it."""
        response = self.client.post(_add_async_tag_url(),
                                    data={'tag-name': 'nonexistent tag'},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        eq_(response.status_code, 200)
        tags_eq(Question.objects.get(pk=1), ['nonexistent tag'])

    def test_add_new_case_insensitive(self):
        """Adding a tag differing only in case from existing ones shouldn't
        create a new tag."""
        self.client.post(_add_async_tag_url(), data={'tag-name': 'RED'},
                         HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        tags_eq(Question.objects.get(pk=1), ['red'])

    def test_add_new_canonicalizes(self):
        """Adding a new tag as an admin should still canonicalize case."""
        response = self.client.post(_add_async_tag_url(),
                                    data={'tag-name': 'RED'},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        eq_(json.loads(response.content)['canonicalName'], 'red')


def _add_tag_url():
    """Return the URL to add_tag for question 1, an untagged question."""
    return reverse('questions.add_tag', kwargs={'question_id': 1})


def _add_async_tag_url():
    """Return the URL to add_tag_async for question 1, an untagged question."""
    return reverse('questions.add_tag_async', kwargs={'question_id': 1})


def _remove_tag_url():
    """Return  URL to remove_tag for question 2, tagged {colorless, green}."""
    return reverse('questions.remove_tag', kwargs={'question_id': 2})


def _remove_async_tag_url():
    """Return URL to remove_tag_async on q. 2, tagged {colorless, green}."""
    return reverse('questions.remove_tag_async', kwargs={'question_id': 2})


class QuestionsTemplateTestCase(TestCaseBase):

    def test_all_filter_highlight(self):
        response = get(self.client, 'questions.questions')
        doc = pq(response.content)
        eq_('active', doc('div#filter ul li')[3].attrib['class'])
        eq_('question-1', doc('ol.questions li')[0].attrib['id'])

    def test_no_reply_filter(self):
        url_ = urlparams(reverse('questions.questions'),
                         filter='no-replies')
        response = self.client.get(url_)
        doc = pq(response.content)
        eq_('active', doc('div#filter ul li')[-1].attrib['class'])
        eq_('question-2', doc('ol.questions li')[0].attrib['id'])

    def test_solved_filter(self):
        # initially there should be no solved answers
        url_ = urlparams(reverse('questions.questions'),
                         filter='solved')
        response = self.client.get(url_)
        doc = pq(response.content)
        eq_('active', doc('div#filter ul li')[5].attrib['class'])
        eq_(0, len(doc('ol.questions li')))

        # solve one question then verify that it shows up
        answer = Answer.objects.all()[0]
        answer.question.solution = answer
        answer.question.save()
        response = self.client.get(url_)
        doc = pq(response.content)
        eq_(1, len(doc('ol.questions li')))
        eq_('question-%s' % answer.question.id,
            doc('ol.questions li')[0].attrib['id'])

    def test_unsolved_filter(self):
        # initially there should be 2 unsolved answers
        url_ = urlparams(reverse('questions.questions'),
                         filter='unsolved')
        response = self.client.get(url_)
        doc = pq(response.content)
        eq_('active', doc('div#filter ul li')[4].attrib['class'])
        eq_(2, len(doc('ol.questions li')))

        # solve one question then verify that it doesn't show up
        answer = Answer.objects.all()[0]
        answer.question.solution = answer
        answer.question.save()
        response = self.client.get(url_)
        doc = pq(response.content)
        eq_(1, len(doc('ol.questions li')))
        eq_(0, len(doc('ol.questions li#question-%s' % answer.question.id)))

    def _my_contributions_test_helper(self, username, expected_qty):
        url_ = urlparams(reverse('questions.questions'),
                         filter='my-contributions')
        self.client.login(username=username, password="testpass")
        response = self.client.get(url_)
        doc = pq(response.content)
        eq_('active', doc('div#filter ul li')[7].attrib['class'])
        eq_(expected_qty, len(doc('ol.questions li')))

    def test_my_contributions_filter(self):
        # jsocol should have 2 questions in his contributions
        self._my_contributions_test_helper('jsocol', 2)

        # pcraciunoiu should have 1 questions in his contributions'
        self._my_contributions_test_helper('pcraciunoiu', 1)

        # rrosario should have 0 questions in his contributions
        self._my_contributions_test_helper('rrosario', 0)

    def test_contributed_badge(self):
        # pcraciunoiu should have a contributor badge on question 1 but not 2
        self.client.login(username='pcraciunoiu', password="testpass")
        response = get(self.client, 'questions.questions')
        doc = pq(response.content)
        eq_(1, len(doc('li#question-1 span.contributed')))
        eq_(0, len(doc('li#question-2 span.contributed')))

    def test_sort(self):
        default = reverse('questions.questions')
        sorted = urlparams(default, sort='requested')

        q = Question.objects.get(pk=2)
        qv = QuestionVote(question=q, anonymous_id='abc123')
        qv.save()

        response = self.client.get(default)
        doc = pq(response.content)
        eq_('question-1', doc('ol.questions li')[0].attrib['id'])

        response = self.client.get(sorted)
        doc = pq(response.content)
        eq_('question-2', doc('ol.questions li')[0].attrib['id'])