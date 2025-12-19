from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q

from .models import Memo
from .utils import normalize_q, parse_sort, now_jst_string

# NOTE: 教材用。わざと“読みにくい/危ない”実装が入っています。
# - legacy=1 の場合、旧実装として“生SQL文字列を組み立てる”検索が動く（危険/壊れやすい）
# - ページネーション無しで一覧が重い
# 目標: Copilot を使って、危険な実装を見つけて安全な形に直す。


def memo_list(request: HttpRequest) -> HttpResponse:
    q = normalize_q(request.GET.get("q"))
    tag = (request.GET.get("tag") or "").strip().lower()
    sort = request.GET.get("sort") or "new"
    legacy = (request.GET.get("legacy") == "1")
    unsafe_sort = (request.GET.get("unsafe_sort") == "1")

    memos = Memo.objects.all()

    # 検索処理（ORM使用で安全に）
    if q:
        memos = memos.filter(Q(title__icontains=q) | Q(body__icontains=q))
    
    if tag:
        memos = memos.filter(tags__name=tag)

    # ソート処理
    sort_field = parse_sort(sort)
    memos = memos.order_by(sort_field)

    context = {
        "memos": memos,
        "q": q,
        "tag": tag,
        "sort": sort,
        "legacy": legacy,
        "unsafe_sort": unsafe_sort
    }
    return render(request, "memos/memo_list.html", context)



def memo_detail(request: HttpRequest, memo_id: int) -> HttpResponse:
    memo = get_object_or_404(Memo, id=memo_id)
    return render(request, "memos/memo_detail.html", {"memo": memo})


def create_memo(request: HttpRequest) -> HttpResponse:
    error = None
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        body = request.POST.get("body") or ""
        tags = request.POST.get("tags") or ""

        if len(title) == 0:
            error = "タイトルは必須です"
        elif len(title) > 120:
            error = "タイトルが長すぎます（120文字まで）"
        else:
            m = Memo(title=title, body=body)
            m.save()
            m.attach_tags_from_csv(tags)
            messages.success(request, f"保存しました ({now_jst_string()})")
            return redirect("memo_detail", memo_id=m.id)

    return render(request, "memos/memo_form.html", {"mode": "新規作成", "memo": {}, "tags": "", "error": error})


def edit_memo(request: HttpRequest, memo_id: int) -> HttpResponse:
    error = None
    memo = get_object_or_404(Memo, id=memo_id)

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        body = request.POST.get("body") or ""
        tags = request.POST.get("tags") or ""

        if len(title) == 0:
            error = "タイトルは必須です"
        elif len(title) > 120:
            error = "タイトルが長すぎます（120文字まで）"
        else:
            memo.title = title
            memo.body = body
            memo.save()

            memo.tags.clear()  # 怪しいところ: 雑に全消し
            memo.attach_tags_from_csv(tags)

            messages.success(request, f"更新しました ({now_jst_string()})")
            return redirect("memo_detail", memo_id=memo.id)

    tag_csv = ",".join([t.name for t in memo.tags.all()])
    return render(request, "memos/memo_form.html", {"mode": "編集", "memo": memo, "tags": tag_csv, "error": error})


def delete_memo(request: HttpRequest, memo_id: int) -> HttpResponse:
    if request.method != "POST":
        messages.error(request, "不正なリクエストです")
        return redirect("memo_list")
    
    memo = get_object_or_404(Memo, id=memo_id)
    memo.delete()
    messages.success(request, "削除しました")
    return redirect("memo_list")
