import torch
from math import copysign

INITIALIZED = False


def _advanced_encode_from_tokens_negpip_wrapper(advanced_encode_from_tokens, from_zero):

    def advanced_encode_from_tokens_negpip(
        tokenized,
        token_normalization,
        weight_interpretation,
        encode_func,
        m_token=266,
        length=77,
        w_max=1.0,
        return_pooled=False,
        apply_to_pooled=False,
    ):
        tokenized_abs = [[(t, abs(w), p) for t, w, p in x] for x in tokenized]
        weights_sign = [[copysign(1, w) for _, w, _ in x] for x in tokenized]

        def _encoded_with_negpip(encode_func, m_token=266, length=77):
            tokens = [[(m_token, 1.0) for _ in range(length)]]
            emb, _ = encode_func(tokens)
            if emb.shape[1] == length:
                return False
            elif emb.shape[1] == length * 2:
                return True
            raise ValueError("Unknown tensor shape - perhaps you've applied NegPip node more than once")

        encoded_with_negpip = _encoded_with_negpip(encode_func, m_token, length)

        def _encode_func(tokens):
            emb, pooled = encode_func(tokens)
            if encoded_with_negpip:
                return emb[:, 0::2, :], pooled
            return emb, pooled

        def _apply_negpip(weights_sign, emb):
            emb_negpip = torch.empty_like(emb).repeat(1, 2, 1)
            emb_negpip[:, 0::2, :] = emb
            emb_negpip[:, 1::2, :] = from_zero(weights_sign, emb)
            return emb_negpip

        weighted_emb, pooled = advanced_encode_from_tokens(
            tokenized_abs,
            token_normalization,
            weight_interpretation,
            _encode_func,
            m_token,
            length,
            w_max,
            return_pooled,
            apply_to_pooled,
        )

        if encoded_with_negpip:
            weighted_emb = _apply_negpip(weights_sign, weighted_emb)

        return weighted_emb, pooled

    return advanced_encode_from_tokens_negpip


def hijack_adv_encode():
    global INITIALIZED
    if not INITIALIZED:
        import sys
        import pathlib

        custom_nodes = pathlib.Path(__file__).parent.parent.parent
        assert custom_nodes.name == "custom_nodes"

        sys.path.insert(0, str(custom_nodes))

        try:

            import custom_nodes.ComfyUI_ADV_CLIP_emb.adv_encode as adv_encode
            import ComfyUI_ADV_CLIP_emb.adv_encode as adv_encode_inner

            advanced_encode_from_tokens_negpip = _advanced_encode_from_tokens_negpip_wrapper(
                adv_encode.advanced_encode_from_tokens, adv_encode.from_zero
            )

            adv_encode.advanced_encode_from_tokens = advanced_encode_from_tokens_negpip
            adv_encode_inner.advanced_encode_from_tokens = advanced_encode_from_tokens_negpip

        except ImportError:
            pass

        finally:
            sys.path.pop(0)
            INITIALIZED = True
