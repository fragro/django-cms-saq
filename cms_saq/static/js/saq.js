// Client-side SAQ question validation and submission, powered by
// Backbone.js.

$(function () {
    // namespace!
    var SAQ = {};

    // so we can fire global SAQ events! awesome!
    _.extend(SAQ, Backbone.Events);

    SAQ.Question = Backbone.Model.extend({
        defaults: {
            value: null
        },
        postValidate: function (attrs) {
            var value = attrs['value'];
            var optional = attrs['optional'] || false;
            console.log(value);
            if (!optional && (value === undefined || value === null || value === "")) {
                return "Please submit an answer to this question.";
            }
        }
    });

    SAQ.QuestionView = Backbone.View.extend({
        events: {
            'change': 'changeValue'
        },
        defaults: {
            value: null
        },
        initialize: function () {
            var self = this;
            this.model.on('error', function (model, error) {
                self.$('.saq-question-error').text(error).show();
            });
            this.model.on('postvalidate', function () {
                self.$('.saq-question-error').hide();
            });
            SAQ.on('submit:start', function () {
                self.$('input, select').attr('disabled','disabled');
            });
            SAQ.on('submit:end', function () {
                self.$('input, select').removeAttr('disabled');
            });
            this.changeValue();
        },
        changeValue: function () {
            // override in subclasses
        }
    });

    SAQ.SingleChoiceQuestionView = SAQ.QuestionView.extend({
        changeValue: function () {
            this.model.set('value', this.$('input:checked').val());
        }
    });

    SAQ.MultiChoiceQuestionView = SAQ.QuestionView.extend({
        changeValue: function () {
            var vals = $.map(this.$('input:checked'), function (el) {
                return $(el).val();
            }).join(",");
            this.model.set('value', vals);
        }
    });

    SAQ.DropDownQuestionView = SAQ.QuestionView.extend({
        changeValue: function () {
            this.model.set('value', this.$('select').val());
        }
    });

    SAQ.FreeTextQuestionView = SAQ.QuestionView.extend({
        changeValue: function () {
            this.model.set('value', this.$('textarea').val());
        }
    });

    SAQ.QuestionCollection = Backbone.Collection.extend({
        model: SAQ.Question,
        validate: function () {
            var passed = true;
            this.forEach(function (question) {
                console.log(question.attributes);
                var msg = question.postValidate(question.attributes);
                if (msg) {
                    question.trigger('error', question, msg);
                    passed = false;
                }
                else {
                    question.trigger('postvalidate');
                }
            });
            return passed;
        },
        asMap: function () {
            return SAQ.questions.reduce(function (data, model) {
                data[model.get('slug')] = model.get('value');
                return data;
            }, {});
        }
    });

    SAQ.questions = new SAQ.QuestionCollection();

    SAQ.FormView = Backbone.View.extend({
        events: {
            'click .saq-next-button': 'submitForms',
            'click .saq-end-button': 'submitFormsAndEnd'
        },
        initialize: function () {
            this.submitting = false;
        },
        submitFormsAndEnd: function(e) {
            return this.submitForms(e, true);
        },
        submitForms: function (e, andEnd) {
            var self = this;
            if (!this.submitting && SAQ.questions.validate()) {
                this.submitting = true;
                this.$('.saq-ticker').css('visibility', 'visible');
                SAQ.trigger('submit:start');
                console.log();
                $.ajax({
                    url: this.options.submitUrl,
                    data: SAQ.questions.asMap(),
                    type: 'POST',
                    error: function (data) { console.log(data); self.onSubmitError(); },
                    success: function (data) {
                        console.log(data);
                        if(data.complete === true){
                            if (andEnd) {
                                self.onSubmitSuccessEnd();
                            } else {
                                self.onSubmitSuccess();
                            }
                        }
                        else{
                            if(data.error){
                              $('#error').html(data.error);
                            }
                            //insert help text
                            if(data.help_text){
                              $('#help_info').show();
                              $('#help_info').html(data.help_text);
                            }
                        }
                        
                    },
                    complete: function () { self.onSubmitComplete(); }
                });
            }
            else {
                console.log("validation failed?");
            }
            return false;
        },
        onSubmitError: function () {
            alert("There was a problem submitting your answers. Please try again later.");
            // TODO we can do better than an alert()
        },
        onSubmitSuccessEnd: function () {
            window.location = this.options.endUrl;
        },
        onSubmitSuccess: function () {
            window.location = this.options.nextUrl;
        },
        onSubmitComplete: function () {
            SAQ.trigger('submit:end');
            this.$('.saq-ticker').css('visibility', 'hidden');
            this.submitting = false;
        }
    });
    window.SAQ = SAQ;
});


// CSRF token protection for AJAX
$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
            // Only send the token to relative URLs i.e. locally.
            xhr.setRequestHeader("X-CSRFToken",
                $('input[name="csrfmiddlewaretoken"]').val());
        }
   }
});

