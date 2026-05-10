from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment
from app.models.battle import Battle, BattleParticipant
from app.models.group_activity import GroupDiscussion, GroupDiscussionParticipant
from app.models.marketplace import MarketplacePurchase
from app.models.message import Message
from app.models.session import ConversationSession
from app.models.stars import StarPaymentOrder, StarWithdrawalRequest
from app.models.summary import Summary
from app.models.token import TokenLedgerEntry
from app.models.user import User
from app.services.admins import normalize_username


async def find_user_for_reset(db: AsyncSession, raw_target: str) -> User | None:
    target = raw_target.strip()
    if not target:
        return None

    if target.isdigit():
        result = await db.execute(select(User).where(User.telegram_id == int(target)))
        return result.scalar_one_or_none()

    username = normalize_username(target)
    result = await db.execute(select(User).where(User.username.ilike(username)))
    return result.scalar_one_or_none()


async def reset_user_profile(db: AsyncSession, user: User) -> None:
    await db.execute(delete(Message).where(Message.user_id == user.id))
    await db.execute(delete(Summary).where(Summary.user_id == user.id))
    await db.execute(delete(TokenLedgerEntry).where(TokenLedgerEntry.user_id == user.id))
    await db.execute(delete(MarketplacePurchase).where(MarketplacePurchase.user_id == user.id))
    await db.execute(delete(BattleParticipant).where(BattleParticipant.user_id == user.id))
    await db.execute(
        delete(GroupDiscussionParticipant).where(GroupDiscussionParticipant.user_id == user.id)
    )
    await db.execute(delete(StarPaymentOrder).where(StarPaymentOrder.user_id == user.id))
    await db.execute(delete(StarWithdrawalRequest).where(StarWithdrawalRequest.user_id == user.id))
    await db.execute(
        update(Battle)
        .where(Battle.created_by_user_id == user.id)
        .values(created_by_user_id=None)
    )
    await db.execute(
        update(GroupDiscussion)
        .where(GroupDiscussion.created_by_user_id == user.id)
        .values(created_by_user_id=None)
    )
    await db.execute(delete(Assessment).where(Assessment.user_id == user.id))
    await db.execute(delete(ConversationSession).where(ConversationSession.user_id == user.id))

    user.status = "object"
    user.lifecycle_status = "newbie"
    user.subjectivity_score = 0
    user.token_balance = 0
    user.profile_summary = None
