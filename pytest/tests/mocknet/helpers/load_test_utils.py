import random
import sys
import time

import base58
from rc import pmap

# Don't use the pathlib magic because this file runs on a remote machine.
sys.path.append('lib')
import mocknet_helpers
import mocknet

from configured_logger import logger


def send_transfer(account, test_accounts, base_block_hash=None):
    dest_account = random.choice(test_accounts)
    amount = 1
    mocknet_helpers.retry_and_ignore_errors(
        lambda: account.send_transfer_tx(dest_account.key.account_id,
                                         transfer_amount=amount,
                                         base_block_hash=base_block_hash))
    logger.info(
        f'Account {account.key.account_id} transfers {amount} yoctoNear to {dest_account.key.account_id}'
    )


def function_call_set_state_then_delete_state(account,
                                              i,
                                              node_account,
                                              test_accounts,
                                              base_block_hash=None):
    assert i < len(function_call_state)

    if not function_call_state[i]:
        action = "add"
    elif len(function_call_state[i]) >= 100:
        action = "delete"
    else:
        action = random.choice(["add", "delete"])

    if action == "add":
        next_id = random.randrange(len(test_accounts))
        next_val = random.randint(0, 1000)
        next_account_id = mocknet.load_testing_account_id(
            node_account.key.account_id, next_id)
        s = f'{{"account_id": "account_{next_val}", "message":"{next_val}"}}'
        logger.info(
            f'Calling function "set_state" of account {next_account_id} with arguments {s} from account {account.key.account_id}'
        )
        tx_res = mocknet_helpers.retry_and_ignore_errors(
            lambda: account.send_call_contract_raw_tx(next_account_id,
                                                      'set_state',
                                                      s.encode('utf-8'),
                                                      0,
                                                      base_block_hash=
                                                      base_block_hash))
        logger.info(
            f'{account.key.account_id} set_state on {next_account_id} {tx_res}')
        function_call_state[i].append((next_id, next_val))
    else:
        assert function_call_state[i]
        item = random.choice(function_call_state[i])
        next_id, next_val = item
        next_account_id = mocknet.load_testing_account_id(
            node_account.key.account_id, next_id)
        s = f'{{"account_id": "account_{next_val}"}}'
        logger.info(
            f'Calling function "delete_state" of account {next_account_id} with arguments {s} from account {account.key.account_id}'
        )
        tx_res = mocknet_helpers.retry_and_ignore_errors(
            lambda: account.send_call_contract_raw_tx(next_account_id,
                                                      'delete_state',
                                                      s.encode('utf-8'),
                                                      0,
                                                      base_block_hash=
                                                      base_block_hash))
        logger.info(
            f'{account.key.account_id} delete_state on {next_account_id} {tx_res}'
        )
        if item in function_call_state[i]:
            function_call_state[i].remove(item)
            logger.info(
                f'Successfully removed {item} from function_call_state. New #items: {len(function_call_state[i])}'
            )
        else:
            logger.info(
                f'{item} is not in function_call_state even though this is impossible. #Items: {len(function_call_state[i])}'
            )


def function_call_ft_transfer_call(account,
                                   node_account,
                                   test_accounts,
                                   base_block_hash=None):
    dest_account = random.choice(test_accounts)
    contract = node_account.key.account_id

    s = f'{{"receiver_id": "{dest_account.key.account_id}", "amount": "3", "msg": "\\"hi\\""}}'
    logger.info(
        f'Calling function "ft_transfer_call" with arguments {s} on account {account.key.account_id} contract {contract} with destination {dest_account.key.account_id}'
    )
    tx_res = mocknet_helpers.retry_and_ignore_errors(
        lambda: account.send_call_contract_raw_tx(contract,
                                                  'ft_transfer_call',
                                                  s.encode('utf-8'),
                                                  1,
                                                  base_block_hash=
                                                  base_block_hash))
    logger.info(
        f'{account.key.account_id} ft_transfer to {dest_account.key.account_id} {tx_res}'
    )


# See https://near.github.io/nearcore/architecture/how/meta-tx.html to understand what is going on.
# Alice pays the costs of Relayer sending 1 yoctoNear to Receiver
def meta_transaction_transfer(alice_account, test_accounts, base_block_hash,
                              base_block_height):
    relayer_account = random.choice(test_accounts)
    receiver_account = random.choice(test_accounts)

    yoctoNearAmount = 1
    transfer_action = transaction.create_payment_action(yoctoNearAmount)
    # Use (relayer_account.nonce + 2) as a nonce to deal with the case of Alice
    # and Relayer being the same account. The outer transaction needs to have
    # a lower nonce.
    # Make the delegated action valid for 10**6 blocks to avoid DelegateActionExpired errors.
    # Value of 10 should probably be enough.
    # DelegateAction is signed with the keys of the Relayer.
    signed_meta_tx = transaction.create_signed_delegated_action(
        relayer_account.key.account_id, receiver_account.key.account_id,
        [transfer_action], relayer_account.nonce + 2, base_block_height + 10**6,
        relayer_account.key.decoded_pk(), relayer_account.key.decoded_sk())

    # Outer transaction is signed with the keys of Alice.
    meta_tx = transaction.sign_delegate_action(signed_meta_tx,
                                               alice_account.key,
                                               relayer_account.key.account_id,
                                               alice_account.nonce + 1,
                                               base_block_hash)
    alice_account.send_tx(meta_tx)
    alice_account.nonce += 1
    relayer_account.nonce += 2

    logger.info(
        f'meta-transaction from {alice_account.key.account_id} to transfer {yoctoNearAmount} yoctoNear from {relayer_account.key.account_id} to {receiver_account.key.account_id}'
    )


def random_transaction(account, i, node_account, test_accounts,
                       max_tps_per_node, base_block_hash, base_block_height):
    time.sleep(random.random() * len(test_accounts) / max_tps_per_node / 3)
    choice = random.randint(0, 3)
    if choice == 0:
        send_transfer(account, test_accounts, base_block_hash=base_block_hash)
    elif choice == 1:
        function_call_set_state_then_delete_state(
            account,
            i,
            node_account,
            test_accounts,
            base_block_hash=base_block_hash)
    elif choice == 2:
        function_call_ft_transfer_call(account,
                                       node_account,
                                       test_accounts,
                                       base_block_hash=base_block_hash)
    elif choice == 3:
        meta_transaction_transfer(account, test_accounts, base_block_hash,
                                  base_block_height)


def send_random_transactions(node_account,
                             test_accounts,
                             max_tps_per_node,
                             rpc_infos=None):
    logger.info("===========================================")
    logger.info("New iteration of 'send_random_transactions'")
    if rpc_infos:
        addr = random.choice(rpc_infos)[0]
    else:
        addr = None
    status = mocknet_helpers.get_status(addr=addr)
    base_block_hash = base58.b58decode(
        status['sync_info']['latest_block_hash'].encode('utf-8'))
    base_block_height = status['sync_info']['latest_block_height']
    pmap(
        lambda index_and_account: random_transaction(
            index_and_account[1],
            index_and_account[0],
            node_account,
            test_accounts,
            max_tps_per_node,
            base_block_hash=base_block_hash,
            base_block_height=base_block_height), enumerate(test_accounts))


def init_ft(node_account):
    tx_res = node_account.send_deploy_contract_tx(
        '/home/ubuntu/fungible_token.wasm')
    logger.info(f'ft deployment {tx_res}')
    mocknet_helpers.wait_at_least_one_block()

    s = f'{{"owner_id": "{node_account.key.account_id}", "total_supply": "{10**33}"}}'
    tx_res = node_account.send_call_contract_raw_tx(node_account.key.account_id,
                                                    'new_default_meta',
                                                    s.encode('utf-8'), 0)
    logger.info(f'ft new_default_meta {tx_res}')


def init_ft_account(node_account, account):
    s = f'{{"account_id": "{account.key.account_id}"}}'
    tx_res = account.send_call_contract_raw_tx(node_account.key.account_id,
                                               'storage_deposit',
                                               s.encode('utf-8'),
                                               (10**24) // 800)
    logger.info(f'Account {account.key.account_id} storage_deposit {tx_res}')

    # The next transaction depends on the previous transaction succeeded.
    # Sleeping for 1 second is the poor man's solution for waiting for that transaction to succeed.
    # This works because the contracts are being deployed slow enough to keep block production above 1 bps.
    mocknet_helpers.wait_at_least_one_block()

    s = f'{{"receiver_id": "{account.key.account_id}", "amount": "{10**18}"}}'
    logger.info(
        f'Calling function "ft_transfer" with arguments {s} on account {account.key.account_id}'
    )
    tx_res = node_account.send_call_contract_raw_tx(node_account.key.account_id,
                                                    'ft_transfer',
                                                    s.encode('utf-8'), 1)
    logger.info(
        f'{node_account.key.account_id} ft_transfer to {account.key.account_id} {tx_res}'
    )
