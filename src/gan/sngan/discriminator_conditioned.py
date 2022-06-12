import numpy as np
import tensorflow as tf
from gan.protein.protein import NUM_AMINO_ACIDS
from gan.sngan.discriminator import Discriminator

from common.model import ops


class GumbelDiscriminatorCond(Discriminator):
    def __init__(self, config, shape, num_classes=None, scope_name=None):
        super(GumbelDiscriminatorCond, self).__init__(config, shape, num_classes, scope_name)
        self.strides = [(1, 2), (1, 2), (1, 2), (1, 2)]
        if self.length == 512:
            self.strides.extend([(1, 2), (1, 2)])




    def network(self, data, labels, reuse):

        # Embedding
        embedding_map_bar = self.get_embeddings(shape=[NUM_AMINO_ACIDS, self.dim])
        h = self.embedding_lookup(data, embedding_map_bar)
        labels1 = labels

        # Resnet
        hidden_dim = self.dim
        for layer in range(len(self.strides)):
            self.log(h.shape)
            block_name, dilation_rate, hidden_dim, strides = self.get_block_params(hidden_dim, layer)
            h = self.add_sn_block(h, hidden_dim, block_name, dilation_rate, strides)
            if layer == 0:
                self.add_attention(h, hidden_dim, reuse)
            if layer == 2:
                embedding_map_bar = self.get_embeddings(shape=[self.num_classes[0], self.embedding_dimension], name = "LABELS_EMBEDDING")
                emb = self.embedding_lookup(labels, embedding_map_bar)
                H, W = h.shape[2], h.shape[3]
                emb = tf.broadcast_to(
                    tf.reshape(emb, (emb.shape[0], emb.shape[1], 1, 1)),
                    (emb.shape[0], emb.shape[1], H, W))
                h = tf.concat([h, emb], axis=1)


        end_block = self.act(h, name="after_resnet_block")
        tf.summary.histogram("after_resnet_block", end_block, family=self.scope_name)
        h_std = ops.minibatch_stddev_layer_v2(end_block)
        tf.summary.histogram("minibatch_stddev_layer", h_std, family=self.scope_name)

        final_conv = ops.snconv2d(h_std, int(hidden_dim / 16), (1, 1), name='final_conv', padding=None)
        self.log(final_conv.shape)
        output = ops.snlinear(tf.squeeze(tf.layers.flatten(final_conv)), 1, name='d_sn_linear')
        tf.summary.scalar("1", tf.cast(
            tf.py_func(lambda x, y: self.print_data(x, y), [tf.squeeze(data), tf.squeeze(output)], tf.double),
            tf.float32))
        return output, end_block


    def print_data(self, x, y):
        arg_max = np.argmax(x, axis=-1)
        var = np.asarray([np.unique(np.transpose(arg_max)[i], return_counts=True)[1].mean() for i in range(128)]).mean()
        print("Max value: {:.5f} | Min value: {:.5f} D Score: {:.5f} | Repeating AA: {:.1f}".format(np.max(x[0]),
                                                                                                    np.min(x[0]),
                                                                                                    y.mean(), var))
        return float(0)
