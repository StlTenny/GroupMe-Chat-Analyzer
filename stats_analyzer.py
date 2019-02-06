import os
import time
import pdb

import urllib2
import json

import peewee
from peewee import *

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


like_matrix = None
mentions_matrix = None
stan_matrix = None
user_names = {}
MATRIX_CACHE = 'matrix_cache.json'

DATABASE = 'groupme.db'
database = SqliteDatabase(DATABASE)

ACTIVE_USERS = [
    975650,
    4055148,
    5430809,
    7036012,
    7461891,
    7629551,
    19828293,
    23955771,
    34370486,
    34842453,
    54065422,
    55077209,
    55182207,
    55320147,
    55520395,
    59724495,
    62629155,
    64010313,
    66033628,
    66102934,
]


class BaseModel(Model):
    class Meta:
        database = database

class GroupChat(BaseModel):
    group_id = IntegerField(unique = True)

class ChatMessage(BaseModel):
    user_id = IntegerField()
    user_name = CharField()
    group_id = IntegerField()
    message_id = IntegerField()
    text = TextField(null=True)
    attachments = TextField(null=True)
    created_at = IntegerField()

    class Meta:
        indexes = (
            (('group_id','message_id'), True),
        )

class FavoritedMessage(BaseModel):
    group_id = IntegerField()
    message_id = IntegerField()
    user_id = IntegerField()
    favorite_id = IntegerField()
    created_at = IntegerField()

    class Meta:
        indexes = (
            (( 'message_id','favorite_id'), True),
        )

class ChatUser(BaseModel):
    group_id = IntegerField()
    user_id = IntegerField()

    class Meta:
        indexes = (
            (('group_id','user_id'), True),
        )

class ChatUserName(BaseModel):
    group_id = IntegerField()
    user_id = CharField()
    user_name = CharField(unique = True)
    last_used = IntegerField()

    class Meta:
        indexes = (
            (('group_id','user_id','user_name'), True),
        )

class ChatMention(BaseModel):
    group_id = IntegerField()
    message_id = IntegerField()
    user_id = IntegerField()
    target_id = IntegerField()
    created_at = IntegerField()

    class Meta:
        indexes = (
            (('group_id','message_id','user_id','target_id'), True),
        )



def find_like_ratio():
    database.connect()
    like_dict = {}
    for user in ChatUser.select():
        like_count = FavoritedMessage.select().where(FavoritedMessage.favorite_id == user.user_id).count()
        message_count = ChatMessage.select().where(ChatMessage.user_id == user.user_id).count()
        like_ratio = float(like_count)/message_count 
        user_name = ChatUserName.select().where(ChatUserName.user_id == user.user_id) \
                .order_by(ChatUserName.last_used.desc()).get().user_name
        dict_key = "%0.2fx-%s" % (like_ratio, user_name)
        like_dict[dict_key] = "%s has a like count of %i, a message count of %i and a like ratio of %0.2fx" % \
                (user_name, like_count, message_count, like_ratio)
    for key in sorted(like_dict.iterkeys(), reverse=True):
        print(like_dict[key])
    database.close()

def find_liked_comments():
    database.connect()
    liked_dict = {}
    for user in ChatUser.select():
        liked_count = FavoritedMessage.select().where(FavoritedMessage.user_id == user.user_id).count()
        message_count = ChatMessage.select().where(ChatMessage.user_id == user.user_id).count()
        user_name = ChatUserName.select().where(ChatUserName.user_id == user.user_id) \
                .order_by(ChatUserName.last_used.desc()).get().user_name
        liked_ratio = float(liked_count) / message_count
        dict_key = "%0.2fx-%s" % (liked_ratio, user_name)
        liked_dict[dict_key] = "%s has sent % i total messages, and has recieved %i total likes. Ratio %0.2fx" % \
                (user_name, liked_count, message_count, liked_ratio)
    for key in sorted(liked_dict.iterkeys(), reverse=True):
        print(liked_dict[key])
    database.close()

def initialize_matrix():
    my_matrix = {}
    i = 0;
    j = 0;
    while i < len(ACTIVE_USERS):
        my_matrix[ACTIVE_USERS[i]] = {}
        #while j < len(ACTIVE_USERS):
        #    my_matrix[ACTIVE_USERS[j]] = 0 
        #    j += 1
        #j=0
        i += 1
    return my_matrix

def populate_matrix_data():
    if os.path.isfile(MATRIX_CACHE):
        populate_from_file()
    else:
        populate_from_db()

def populate_from_file():
    global like_matrix, mentions_matrix, stan_matrix, user_names
    with open(MATRIX_CACHE) as cache:
        cache_data = json.load(cache)
    like_matrix = cache_data['like_matrix']
    mentions_matrix = cache_data['mentions_matrix']
    stan_matrix = cache_data['stan_matrix']
    user_names = cache_data['user_names']

def populate_from_db():
    global like_matrix, mentions_matrix, stan_matrix, user_names
    database.connect()
    i = 0;
    j = 0;
    like_matrix = initialize_matrix()
    mentions_matrix = initialize_matrix()
    stan_matrix = initialize_matrix()
    while i < len(ACTIVE_USERS):
        j=i
        while j < len(ACTIVE_USERS):
            a_user = ChatUser.select().where(ChatUser.user_id == ACTIVE_USERS[i]).get()
            b_user = ChatUser.select().where(ChatUser.user_id == ACTIVE_USERS[j]).get()

            a_name = ChatUserName.select().where(ChatUserName.user_id == a_user.user_id) \
                .order_by(ChatUserName.last_used.desc()).get().user_name
            b_name = ChatUserName.select().where(ChatUserName.user_id == b_user.user_id) \
                .order_by(ChatUserName.last_used.desc()).get().user_name
            a_first_message_time = ChatMessage.select().where(ChatMessage.user_id == a_user.user_id).order_by(ChatMessage.created_at).get().created_at
            b_first_message_time = ChatMessage.select().where(ChatMessage.user_id == b_user.user_id).order_by(ChatMessage.created_at).get().created_at
            earliest_message = max(a_first_message_time, b_first_message_time)
            a_message_count = ChatMessage.select().where(ChatMessage.user_id == a_user.user_id).where(ChatMessage.created_at > earliest_message).count()
            b_message_count = ChatMessage.select().where(ChatMessage.user_id == b_user.user_id).where(ChatMessage.created_at > earliest_message).count()
            a_likes_b_count = FavoritedMessage.select().where(FavoritedMessage.user_id == b_user.user_id) \
                .where(FavoritedMessage.favorite_id == a_user.user_id).count()
            b_likes_a_count = FavoritedMessage.select().where(FavoritedMessage.user_id == a_user.user_id) \
                .where(FavoritedMessage.favorite_id == b_user.user_id).count()
            a_mentions_b_count = ChatMention.select().where(ChatMention.user_id == a_user.user_id) \
                .where(ChatMention.target_id == b_user.user_id).count()
            b_mentions_a_count = ChatMention.select().where(ChatMention.user_id == b_user.user_id) \
                .where(ChatMention.target_id == a_user.user_id).count()
            messages_since_both = ChatMessage.select().where(ChatMessage.created_at > earliest_message).count()
            a_likes_messages_count = FavoritedMessage.select().where(FavoritedMessage.favorite_id == a_user.user_id) \
                    .where(FavoritedMessage.created_at > earliest_message).count()
            b_likes_messages_count = FavoritedMessage.select().where(FavoritedMessage.favorite_id == b_user.user_id) \
                    .where(FavoritedMessage.created_at > earliest_message).count()
            a_mentions_people_count = ChatMention.select().where(ChatMention.user_id == a_user.user_id) \
                    .where(ChatMention.created_at > earliest_message).count()
            b_mentions_people_count = ChatMention.select().where(ChatMention.user_id == b_user.user_id) \
                    .where(ChatMention.created_at > earliest_message).count()

            if a_mentions_people_count == 0:
                a_mentions_people_count = 100000000000;
            if b_mentions_people_count == 0:
                b_mentions_people_count = 100000000000;
            if a_likes_messages_count == 0:
                a_likes_messages_count = 100000000000;
            if b_likes_messages_count == 0:
                b_likes_messages_count = 100000000000;
            if a_message_count == 0:
                a_message_count = 100000000000;
            if b_message_count == 0:
                b_message_count = 100000000000;

            total_other_people = len(ACTIVE_USERS)


            # Calculate the inverse Counts
            a_likes_others_count = a_likes_messages_count - a_likes_b_count
            b_likes_others_count = b_likes_messages_count - b_likes_a_count

            a_mentions_others_count = a_mentions_people_count - a_mentions_b_count
            b_mentions_others_count = b_mentions_people_count - b_mentions_a_count


            # Set Counts Super high if zero
            if a_likes_others_count == 0:
                a_likes_others_count = 100000000000;
            if b_likes_others_count == 0:
                b_likes_others_count = 100000000000;
            if a_mentions_others_count == 0:
                a_mentions_others_count = 100000000000;
            if b_mentions_others_count == 0:
                b_mentions_others_count = 100000000000;

            # Calculate the rates
            a_likes_others_rate =  ((float(a_likes_others_count) / a_likes_messages_count) / total_other_people)
            a_likes_b_rate = float(a_likes_b_count) / a_likes_messages_count
            a_prefers_b_rate = float(a_likes_b_rate) / a_likes_others_rate


            b_likes_others_rate =  ((float(b_likes_others_count) / b_likes_messages_count) / total_other_people)
            b_likes_a_rate = float(b_likes_a_count) / b_likes_messages_count
            b_prefers_a_rate = float(b_likes_a_rate) / b_likes_others_rate

            a_mentions_others_rate = ((float(a_mentions_others_count)/ a_mentions_people_count) / total_other_people)
            a_mentions_b_rate = float(a_mentions_b_count) / a_mentions_people_count
            a_targets_b_rate = float(a_mentions_b_rate) / a_mentions_others_rate

            if a_targets_b_rate < 1 and a_targets_b_rate > 0:
                a_targets_b_rate = -1/float(a_targets_b_rate)
            if a_targets_b_rate < -10:
                a_targets_b_rate = -10

            b_mentions_others_rate = ((float(b_mentions_others_count)/ b_mentions_people_count) / total_other_people)
            b_mentions_a_rate = float(b_mentions_a_count) / b_mentions_people_count
            b_targets_a_rate = float(b_mentions_a_rate) / b_mentions_others_rate

            if b_targets_a_rate < 1 and b_targets_a_rate > 0:
                b_targets_a_rate = -1/float(b_targets_a_rate)
            if b_targets_a_rate < -10:
                b_targets_a_rate = -10

            # Scale data around .5. where .5 = 1.

            a_expected_to_mention_b_count = (float(b_message_count) / messages_since_both) * a_mentions_people_count
            b_expected_to_mention_a_count = (float(a_message_count) / messages_since_both) * b_mentions_people_count

            a_true_rate = float(a_mentions_b_count) / a_expected_to_mention_b_count
            b_true_rate = float(b_mentions_a_count) / b_expected_to_mention_a_count

            if a_true_rate < 1 and a_true_rate > 0:
                a_true_rate = -1/float(a_true_rate)
            if b_true_rate < 1 and b_true_rate > 0:
                b_true_rate = -1/float(b_true_rate)

            a_true_rate = min(5, a_true_rate)
            a_true_rate = max(-5, a_true_rate)
            b_true_rate = min(5, b_true_rate)
            b_true_rate = max(-5, b_true_rate)

            print("%s should mention %s %.2f times" %(a_name, b_name, a_expected_to_mention_b_count))
            print("%s is mentioned %.2f times" % ( b_name, a_mentions_b_count))
            print("%s is mentioned at a rate %.2f" % ( b_name, a_true_rate))


            print("%s mentions %s at a rate of %.2f their average" % (a_name, b_name, a_targets_b_rate))
            print("%s likes %s messages at a rate of %.2f their average" % (a_name, b_name, a_prefers_b_rate))
            print("")
            print("")
            print("%s mentions %s at a rate of %.2f their average" % (b_name, a_name, b_targets_a_rate))
            print("%s likes %s messages at a rate of %.2f their average" % (b_name, a_name, b_prefers_a_rate))
            print("")
            print("")

            # Calculate the ratios
            a_mentions_people_ratio = float(a_mentions_people_count) / a_message_count
            b_mentions_people_ratio = float(b_mentions_people_count) / b_message_count

            a_mentions_b_ratio = float(a_mentions_b_count) / a_message_count
            b_mentions_a_ratio = float(b_mentions_a_count) / b_message_count

            a_mentions_b_percentage = float(a_mentions_b_count) / a_mentions_people_count
            b_mentions_a_percentage = float(b_mentions_a_count) / b_mentions_people_count


            a_likes_messages_ratio = float(a_likes_messages_count) / messages_since_both
            b_likes_messages_ratio = float(b_likes_messages_count) / messages_since_both
            a_likes_b_ratio = float(a_likes_b_count) / b_message_count
            b_likes_a_ratio = float(b_likes_a_count) / a_message_count

            a_likes_b_percentage = float(a_likes_b_count) / a_likes_messages_count
            b_likes_a_percentage = float(b_likes_a_count) / b_likes_messages_count

            #a_likes_diff = a_likes_b_percentage - b_likes_a_percentage
            #b_likes_diff = b_likes_a_percentage - a_likes_b_percentage

            a_likes_diff = a_prefers_b_rate - b_prefers_a_rate
            b_likes_diff = b_prefers_a_rate - a_prefers_b_rate

            a_mentions_diff = a_targets_b_rate - b_targets_a_rate
            b_mentions_diff = b_targets_a_rate - a_targets_b_rate

            a_stan_b_rate = a_likes_diff + a_mentions_diff
            b_stan_a_rate = b_likes_diff + b_mentions_diff


            #a_mentions_diff = a_mentions_b_ratio - a_mentions_people_ratio
            #b_mentions_diff = b_mentions_a_percentage - a_mentions_b_percentage

            #a_stan_b_rate = a_likes_diff + a_mentions_diff
            #b_stan_a_rate = b_likes_diff + b_mentions_diff

            # Populate the matricies

            user_names[a_user.user_id] = a_name.split()[0]
            user_names[b_user.user_id] = b_name.split()[0]

            like_matrix[a_user.user_id][b_user.user_id] = a_likes_diff
            like_matrix[b_user.user_id][a_user.user_id] = b_likes_diff

            mentions_matrix[a_user.user_id][b_user.user_id] = a_targets_b_rate
            mentions_matrix[b_user.user_id][a_user.user_id] = b_targets_a_rate

            mentions_matrix[a_user.user_id][b_user.user_id] = a_true_rate
            mentions_matrix[b_user.user_id][a_user.user_id] = b_true_rate

            stan_matrix[a_user.user_id][b_user.user_id] = a_stan_b_rate
            stan_matrix[b_user.user_id][a_user.user_id] = b_stan_a_rate


            j+=1
        i += 1

    cache_data = {}
    cache_data['like_matrix'] = like_matrix
    cache_data['mentions_matrix'] = mentions_matrix
    cache_data['stan_matrix'] = stan_matrix
    cache_data['user_names'] = user_names
    with open(MATRIX_CACHE, 'w') as cache:
        json.dump(cache_data, cache)


    database.close()
    # iterate through each pair of people
    # find first message available
    # count messages for each person 
    # count likes for each person 
    # count mentions for each person
    # fill in array 

def populate_heat_map(seed_matrix):
    df = pd.DataFrame.from_dict(seed_matrix)
    df = df.transpose()
    df.rename(columns=user_names,index=user_names,inplace=True)
    output = sns.heatmap(df,cmap='PiYG',center=1)
    plt.show()


if __name__ == '__main__':
    #find_like_ratio()
    #find_liked_comments()
    #like_you_heatmap()
    populate_matrix_data()
    populate_heat_map(mentions_matrix)
