# Cloudify Kubernetes Plugin - examples 

## application-migration-blueprint

Example of moving nodecellar kubernetes application from one kuberentes node to another.
Uses *cloudify-kubernetes-plugin*, *cloudify-utilities-plugin* (*configuration*) and *configuration_update* workflow

### Design

Blueprint contains node-cellar application consists of 2 Deployments: Mongo DB and Node JS and one service which is exposing application.
This application which is using native cloudify-kubernetes-plugin you can find [here](https://github.com/cloudify-examples/nodecellar-kubernetes-blueprint).

To enable movement of application between Kubernetes nodes two additional node types has been introduced in this blueprint:
 
 * **MovableKubernetesResourceTemplate** - its role it to render Kubernetes YAML resource definition (defined in *definition* property) with node selector containing proper label.
   On lifecycle events python script *scripts/render_template.py* is run.
   This script is taking resource definition from *definiton* property and label from runtime properties injected by utilities (configuration) plugin.
   Name of this runtime property is defined in *param_name* property.
   Finally python script renders template as *result* runtime property.
 * **MovableDeployment** - it is kind wrapper of standard *cloudify.kubernetes.resources.Deployment type. 
   Only one difference it that it contains additional properties to enable *configuration_update* workflow to be run on it.
   Please note that all node templates made from this type are taking input definition ***dynamically*** from runtime property *result* of some *MovableKubernetesResourceTemplate* node template.
 
Updating existing Kubernetes resources is done using native Kubernetes API methods called on *update* lifecycle event.
So Kubernetes plugin is not aware of scheduling, deletion of old resources, creation of new resources etc. 
All things are done using update request by Kubernetes scheduler, so this approach should ensure minimal time of application unavailability. 
 
### Prerequisites

* **Environment** - you should have working Kubernetes cluster with at least two nodes (you can have master and node on the same VM).
 Setup used for development of this example was:
   * Cloudify Manager created using [cloudify-environment-setup blueprint](https://github.com/cloudify-examples/cloudify-environment-setup)
   * Kubernetes cluster created using [simple-kubernetes-blueprint](https://github.com/cloudify-examples/simple-kubernetes-blueprint)

* **Kubernetes nodes with labels** - when your cluster is ready, you need to put a labels for two Kubernetes nodes. 
  You can do it using *kubectl* CLI:
 
  ```
  kubectl label nodes <node_nameX> demo=nodeX
  ```

### Demo

1) **Prepare inputs file** - create new YAML file e.g. *inputs.yaml*. Place mentioned below keys with data in this file:
* ***kubernetes_configuration_file_content*** - Configuration of the kubernetes master.
  It can be retrieved using command:
  ```
  kubectl config view --raw
  ```
* ***external_ip*** - IP for the end user/Floating IP. Should be one of the Kubernetes VM interfaces
* ***external_port*** - port for the end-user access. Default is *8080*
* ***parameters_json*** - node_label put on Kubernetes node on which application should be installed initially. Example:
```
parameters_json:
  node_label:
    demo: node1
```

2) **Install application on first node**
```
cfy install blueprint.yaml -d demo -i inputs.yaml 
```

3) **Check application**

Check if all Kubernetes resources has been provisioned successfully (and are placed on proper node):

```
kubectl get all -a -o wide
```

Check in your browser (if you can reach Kubernetes cluster) if application is running:

```
http://<external_ip>:<external_port>
```


4) **Move application from first node to second node** - it will be done by running *configuration_update* workflow.
   It have to be run for two node types: first *MovableKubernetesResourceTemplate* (to prepare kubernetes resources YAML template)
   and then *MovableDeployment* (provison created template and update existing Kubernetes resources).
   
   Parameter with value *node2* in presented below invocations should be label of Kubernetes node where this application should be finally moved.

```
cfy execution start configuration_update -d demo -p '{"node_types_to_update": ["MovableKubernetesResourceTemplate"], "params": {"node_label": {"demo": "node2"}}, "configuration_node_type": "configuration_loader"}'
cfy execution start configuration_update -d demo -p '{"node_types_to_update": ["MovableDeployment"], "params": {"node_label": {"demo": "node2"}}, "configuration_node_type": "configuration_loader"}'
```

5) **Check application**


Check if all Kubernetes resources has been moved to new node:

```
kubectl get all -a -o wide
```

Check in your browser (if you can reach Kubernetes cluster) if application is running:

```
http://<external_ip>:<external_port>
```

6) **Uninstall appliaction**

```
cfy uninstall demo
```

## cassandra-blueprint
TODO

## load-balancer-blueprint
TODO

## openstack-node-existing-cluster
TODO

## persistent-volumes-blueprint
TODO

## replicasets-blueprint
TODO

## replication-controller-blueprint
TODO

## simple-blueprint-defined-resource
TODO

## simple-custom-blueprint-defined-resource
TODO

## simple-file-defined-resource
TODO

## simple-multiple-file-defined-resource
TODO

## wordpress-blueprint
TODO
