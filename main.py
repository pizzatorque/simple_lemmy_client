from __future__ import annotations

from dataclasses import dataclass
from pprint import pprint

import requests
from simple_term_menu import TerminalMenu


@dataclass(frozen=True)
class Creator:
    _id: str
    name: str


@dataclass(frozen=True)
class Comment:
    community: str
    creator: str
    downvotes: int
    upvotes: int
    _id: str
    body: str
    url: str

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
        return f"{self.title[:50]}::⬆️ {self.upvotes}::⬇️ {self.downvotes}"

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


class PostPage:
    post: Post
    url = "https://lemmy.ml/api/v3/post"
    headers = {"accept": "application/json"}

    def __init__(self, post: Post):
        self.post = post

    def get_post_contents(self):
        url = self.url + "?id=" + self.post._id
        response: dict = requests.get(url, headers=self.headers).json()
        pprint(response)


class CommentsPage:
    post: Post
    url = "https://lemmy.ml/api/v3/comment/list"
    headers = {"accept": "application/json"}
    comments: list[Comment] = []

    def __init__(self, post: Post):
        self.post = post

    def get_comment_body(self, partial_body: str):
        for c in self.comments:
            if c.body.startswith(partial_body):
                return c.body

    def get_comments(self):
        url = (
            self.url
            + f"?GetComments=type_=Local&sort=Hot&post_id={self.post._id}&community_name={self.post.community}"
        )
        response = requests.get(url, headers=self.headers).json()["comments"]
        self.comments.extend([Comment.from_dict(d) for d in response])
        menu = TerminalMenu(
            [c.body[:50] for c in self.comments],
            title="Comments",
            preview_border=True,
            preview_command=self.get_comment_body,
        )
        val = menu.show()
        pprint(self.comments[val])


class Home:
    posts: list[Post] = []
    url = "https://lemmy.ml/api/v3/post/list?type_=Local&sort=Hot"
    headers = {"accept": "application/json"}

    def get_post_body(self, name: str):
        posts = [i for i in self.posts if i.title.startswith(name.split("::")[0])]
        post = posts[0]
        return post.display_post_contents()

    def get_posts(self):
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
        return CommentsPage(self.posts[val]).get_comments()


def main():
    Home().get_posts()


if __name__ == "__main__":
    main()
