from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from pprint import pprint
from typing import Any, Protocol, runtime_checkable

import requests
from simple_term_menu import TerminalMenu


@dataclass(frozen=True)
class Creator:
    _id: str
    name: str


@dataclass(frozen=True)
class Comment:
    _id: str  # 0.123.333.222
    community: str
    creator: str
    downvotes: int
    upvotes: int
    body: str
    url: str
    path: str

    @classmethod
    def from_dict(cls, d: dict) -> Comment:
        return cls(
            community=d["community"]["name"],
            creator=d["creator"]["name"],
            downvotes=d["counts"]["downvotes"],
            upvotes=d["counts"]["upvotes"],
            _id=str(d["comment"]["id"]),
            body=d["comment"]["content"],
            url=d["comment"]["ap_id"],
            path=d["comment"].get("path", ""),
        )


@dataclass(frozen=True)
class Post:
    title: str
    community: str
    creator: str
    comments: int
    downvotes: int
    upvotes: int
    _id: str
    body: str
    url: str

    def to_menu_entry(self):
        return f"{self.title[:50]}::⬆️ {self.upvotes}::⬇️ {self.downvotes} ::💬 {self.comments}"

    @property
    def score(self):
        return self.upvotes - self.downvotes

    @classmethod
    def from_dict(cls, d: dict) -> Post:
        return cls(
            title=d["post"]["name"],
            community=d["community"]["name"],
            _id=str(d["post"]["id"]),
            creator=d["creator"]["name"],
            comments=d["counts"]["comments"],
            downvotes=d["counts"]["downvotes"],
            upvotes=d["counts"]["upvotes"],
            body=d["post"].get("body", ""),
            url=d["post"].get("url", ""),
        )

    def display_post_contents(self) -> str:
        return (
            f"🔈{self.community} ::"
            + f"👤{self.creator} :: "
            + f"💬 {self.comments}"
            + f"\n{self.body if self.body else self.url}"
        )


class Context:
    prev_page: list[type[Displayer]]
    objs: dict[str, Any]

    def __init__(self, prev_page: list[type[Displayer]] = [], objs={}):
        self.prev_page = prev_page
        self.objs = objs


class Page(ABC):
    url: str
    headers: dict[str, str]
    context: Context


@runtime_checkable
class Displayer(Protocol):
    def __init__(self, context: Context): ...

    def display(self) -> None: ...


class CommentsPage(Page):
    post: Post
    url = "https://lemmy.ml/api/v3/comment/list"
    headers = {"accept": "application/json"}
    sorted_comments: dict[str, Comment]
    context: Context
    comments: list[Comment] = []

    def __init__(self, context: Context):
        self.context = context
        print(self.context.prev_page)

    def get_comment_body(self, partial_body: str):
        key = partial_body.split(":::")[0]
        body: str = self.sorted_comments[key].body
        lines = body.split()
        for l in range(len(lines)):
            if not l % 10 and l:
                lines[l] = lines[l] + "\n"
        return " ".join(lines)

    def display(self) -> None:
        url = (
            self.url
            + f"?GetComments=type_=Local&limit=30&max_depth=3&sort=Hot&post_id={self.context.objs["post"]._id}&community_name={self.context.objs["post"].community}"
        )
        response = requests.get(url, headers=self.headers).json()["comments"]
        self.comments.extend([Comment.from_dict(d) for d in response])
        cd = {c.path: c for c in self.comments}
        self.sorted_comments: dict[str, Comment] = dict(sorted(cd.items()))
        menu = TerminalMenu(
            [
                f"{k}:::{c.body}"[:60].replace("\n", " ")
                for k, c in self.sorted_comments.items()
            ],
            accept_keys=("enter", "alt-d", "backspace"),
            title="Comments",
            preview_border=True,
            preview_command=self.get_comment_body,
        )
        val = menu.show()
        self.context.prev_page.append(CommentsPage)
        match menu.chosen_accept_key:
            case "backspace":
                self.context.prev_page = self.context.prev_page[:-1]
                self.context.objs.pop("post")
                self.context.prev_page[-1](self.context).display()
            case _:
                print(val)


class CustomHome(Page):
    posts: list[Post] = []
    url = "https://lemmy.ml/api/v3/post/list?type_=Local&sort=Hot&limit=10&community_name={}"
    headers = {"accept": "application/json"}
    context: Context

    def __init__(self, context: Context):
        self.context = context
        community_name = context.objs["community_name"]
        self.url = self.url.format(community_name)
        print(self.context.prev_page)

    def get_post_body(self, name: str):
        posts = [i for i in self.posts if i.title.startswith(name.split("::")[0])]
        post = posts[0]
        return post.display_post_contents()

    def display(self):
        response: dict = requests.get(self.url, headers=self.headers).json()
        raw_posts: list[dict] = [p for p in response.get("posts", [])]
        self.posts = [Post.from_dict(p) for p in raw_posts]
        menu = TerminalMenu(
            [p.to_menu_entry() for p in self.posts],
            title="Posts",
            accept_keys=("enter", "alt-d", "backspace"),
            preview_border=True,
            preview_command=self.get_post_body,
        )
        val: int = menu.show()

        if self.context.prev_page[-1] != type(self):
            self.context.prev_page.append(CustomHome)
        match menu.chosen_accept_key:
            case "backspace":
                print("BEFORE::", self.context.prev_page)
                self.context.prev_page = self.context.prev_page[:-1]
                print("AFTER::", self.context.prev_page)
                self.context.prev_page[-1](self.context).display()
            case _:
                self.context.objs["post"] = self.posts[val]
                CommentsPage(context=self.context).display()


class LocalHome(Page):
    posts: list[Post] = []
    url = "https://lemmy.ml/api/v3/post/list?type_=Local&sort=TopYear&limit=10"
    headers = {"accept": "application/json"}
    context: Context

    def __init__(self, context: Context):
        self.context = context
        print(self.context.prev_page)

    def get_post_body(self, name: str):
        posts = [i for i in self.posts if i.title.startswith(name.split("::")[0])]
        post = posts[0]
        return post.display_post_contents()

    def display(self):
        response: dict = requests.get(self.url, headers=self.headers).json()
        raw_posts: list[dict] = [p for p in response.get("posts", [])]
        self.posts = [Post.from_dict(p) for p in raw_posts]
        menu = TerminalMenu(
            [p.to_menu_entry() for p in self.posts],
            title="Posts",
            preview_border=True,
            preview_command=self.get_post_body,
        )
        val: int = menu.show()
        self.context.objs["post"] = self.posts[val]
        self.context.prev_page.append(LocalHome)
        CommentsPage(context=self.context).display()


class MyCommunities(Page):
    url: str = ""
    headers: dict[str, str] = {}
    context: Context
    communities: list[str] = ["linux"]

    def __init__(self, context: Context) -> None:
        self.context = context
        self.communities = context.objs["communities"]
        print(self.context.prev_page)

    @classmethod
    def from_communities(cls, c: list[str], context: Context):
        context.objs["communities"] = c
        my_communities = cls(context)
        my_communities.communities = c
        return my_communities

    def display(self):
        menu = TerminalMenu(
            self.communities,
            title="Communities 💬",
        )
        val: int = menu.show()
        self.context.objs["community_name"] = self.communities[val]
        if not len(self.context.prev_page):
            self.context.prev_page.append(MyCommunities)
        CustomHome(self.context).display()


def __is_displayer(_: type[Displayer]):
    return


__is_displayer(LocalHome)
__is_displayer(CommentsPage)
__is_displayer(MyCommunities)
__is_displayer(CustomHome)


def main():
    my_communities = ["linux", "green"]
    MyCommunities.from_communities(my_communities, Context()).display()
    # TODO: CONTEXT SHOULD KEEP TRACK OF PREVIOUS ARGUMENTS TO CLASSES, AVOID CLASSMETHODS, PUT ARGUMENTS IN CONTEXT INSTEAD


if __name__ == "__main__":
    main()
