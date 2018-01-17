slack-beebot
====================================================

Beebot is a python slack bot that counts and reports on users reactions.
It uses the Slack RTM API and the slackclient library.

.. |build-status|

QuickStart
==========

1. Clone the git repository:

    git clone git@github.com:allred/slack-beebot.git

2. Install pyenv

    Follow instructions at https://github.com/pyenv/pyenv-installer

    pyenv install 3.6.4

    pyenv virtualenv beebot 3.6.4

    pyenv activate beebot

3. Install required libraries:

    pip install -r requirements.txt

4. Add a Bot integration in Slack and get the token

5. Set environmental variables:

	export SLACK_BOT_TOKEN="xoxb-111111111111-XXXXXXXXXXXXXXXXXXXXXXXX"

6. Run Beebot:

	cd slack-beebot && python beebot.py

7. Invite the bot to a channel which will be monitored

8. Direct-message the bot for usage info

	showme usage

Requirements
============

slack-beebot requires the following:

* Python 3.6+
* slackclient

.. |build-status| image:: https://travis-ci.org/itzo/slack-beebot.svg?branch=master
   :target: https://travis-ci.org/itzo/slack-beebot
   :alt: Build status
